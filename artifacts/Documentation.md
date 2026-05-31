# BPSR-Fishing-Bot-DS — Technical Documentation

> **Fork of** [`hyuse98/BPSR-Fishing-Bot`](https://github.com/hyuse98/BPSR-Fishing-Bot)
> **Fork owner:** `saptia14`  ·  **Fork name:** `BPSR-Fishing-Bot-DS` ("DS" = Demon Soul edition)
> **License:** GPL-3.0  ·  **Language:** Python 3.8+  ·  **Status of upstream:** archived/unmaintained by original author

This document describes *what the project is*, *how it works*, the *tech stack*, the *methodology and algorithms* it uses, the *problem it solves and how*, and the *purpose of every file* in the repository.

---

## 1. What the project is

**BPSR-Fishing-Bot** is an automated, open-source fishing bot for the MMORPG **Blue Protocol: Star Resonance** (BPSR). It plays the in-game fishing minigame end-to-end with **zero memory injection and zero packet manipulation** — it works purely by *looking at the screen* (computer-vision template matching) and *simulating human keyboard/mouse input*. Because it never touches the game's process or network, it behaves like an extremely fast, tireless human player.

The bot can run for hours unattended: it casts the line, waits for a bite, plays the catch minigame, automatically swaps a broken rod for a new one, handles disconnect/reconnect prompts, and recovers from unexpected states via timeouts.

---

## 2. The problem it solves (and how)

| Problem | How the bot solves it |
|---|---|
| Fishing in BPSR is repetitive grinding (cast → wait → react → confirm, hundreds of times). | Fully automates the loop as a **Finite State Machine** so the player never touches the keyboard. |
| The catch minigame requires *reaction-timed* left/right inputs. | Detects the on-screen **left/right arrow** prompts via template matching and holds the matching `A`/`D` key, switching instantly when the arrow flips. |
| Rods break and must be re-equipped, otherwise fishing silently stops. | A dedicated `CHECKING_ROD` state verifies a valid rod icon (`flex`/`sturdy`/`reg`) is present; if not, it opens the menu (`M`) and clicks a fixed equip slot to replace it. |
| The game can throw unexpected UI (level-up popup, server-connect dialog, fish escapes). | **Interceptors / guard rails** and dedicated detections catch these and steer the FSM back to a safe state. |
| The bot could get stuck (missed event, frozen UI). | The state machine enforces **per-state timeouts**; on expiry it releases all inputs, presses `ESC`, and resets to `STARTING`. |
| Game visuals can shift between patches, breaking detection. | Detection is **data-driven**: swap a PNG template and/or lower the `precision` value — no code changes required. |
| Searching a 1920×1080 frame every loop is slow. | Each template is restricted to a small **Region Of Interest (ROI)** rectangle, with an optional **concentric-square pixel search** to tolerate small positional drift. |

---

## 3. Tech stack

| Layer | Technology | Role in the project |
|---|---|---|
| Language | **Python 3.8+** | Entire codebase. |
| Screen capture | **`mss` 10.x** | Very fast, low-latency monitor/region grabbing into NumPy arrays. |
| Computer vision | **OpenCV (`opencv-python` 4.12)** | `cv.matchTemplate` (TM_CCOEFF_NORMED) template matching with optional alpha mask; color conversion; grayscale matching. |
| Numerics | **NumPy** | Wraps raw screenshots as arrays for OpenCV. |
| Keyboard input | **`pydirectinput`** (scancode) with **PyAutoGUI** fallback | Scancode `SendInput` that DirectX/Unity games honor; PyAutoGUI used for absolute mouse moves/clicks. |
| Global hotkeys | **`keyboard` 0.13.5** | System-wide `7`/`8`/`9` hotkeys to pause, stop, and toggle the ROI overlay. |
| Window discovery | **`ctypes` Win32 (`winutil.py`)** | Enumerates top-level windows, scores the real game client vs. the launcher, reads the exact **client rect**, DPI scale, and process elevation — no third-party dependency. |
| Packaging | **PyInstaller** | Builds standalone `Doctor.exe` and `BPSR-Fishing.exe` with templates bundled. |
| Debug overlay GUI | **PyQt6 6.10 (+ `pyqt6-sip`)** | Optional, lazily-imported transparent overlay (`roi_visualizer.py`) drawing every ROI rectangle for tuning. |
| Concurrency | **`multiprocessing`** (stdlib) | Runs the ROI visualizer in a separate process so it doesn't block the bot loop. |

> **Resolution-independent (DS edition).** ROIs and templates are calibrated against a 1920×1080 reference and **auto-scaled** to the live window size, so any resolution, windowed/full-screen, multi-monitor and non-100% display scaling all work without re-tuning. See §14.

---

## 4. Architecture overview

The bot is built around a **Finite State Machine (FSM)** plus a thin set of game-facing services. Solid OOP boundaries (abstract base classes, a shared `BotComponent` mixin, dependency injection of the `bot` object) keep each piece single-responsibility and easy to extend.

```
main.py
  └── FishingBot (core/fishing_bot.py)         ← owns everything, runs the update() loop
        ├── Config            (config/)         ← screen + detection + bot settings
        ├── Detector          (core/game/)      ← screen capture + template matching
        ├── GameController     (core/game/)      ← keyboard/mouse simulation
        ├── StatsTracker       (core/stats.py)   ← session counters
        ├── LevelCheckInterceptor (core/interceptors/) ← guard rail
        └── StateMachine       (core/state/)     ← current state + transitions + timeouts
              └── 6 concrete States (core/state/impl/)
```

### Main loop (`main.py` → `FishingBot.update()`)
1. `Hotkeys` registers global `7/8/9` keys. The bot starts **paused**.
2. While not stopped: if not paused, call `bot.update()`, then `sleep(0.1)`.
3. `update()` grabs one screen frame (`Detector.capture_screen`) and passes it to `StateMachine.handle(screen)`.
4. Optional FPS throttling via `target_fps` (`0` = unlimited).
5. On stop: print stats and release all held inputs.

### State machine (`core/state/state_machine.py`)
- Holds a dict `{StateType: stateInstance}` and the current state + start time.
- `handle(screen)`: **first** checks the active state's timeout; if exceeded → release controls, press `ESC`, record a `timeout`, force-reset to `STARTING`. Otherwise it calls `current_state.handle(screen)`, which **returns the next `StateType`**, and transitions to it.
- Transitions are logged; re-entering the same state is a no-op unless `force=True`.

---

## 5. The fishing state graph (algorithm)

Each state's `handle(screen)` inspects the frame and returns the next state. `StateType` (`core/state/state_type.py`) enumerates: `STARTING, CHECKING_ROD, CASTING_BAIT, WAITING_FOR_BITE, PLAYING_MINIGAME, FINISHING`.

```
                 ┌─────────────────────────────────────────────┐
                 ▼                                             │
   ┌──────────┐   ┌──────────────┐   ┌──────────────┐   ┌─────────────────┐
   │ STARTING │──▶│ CHECKING_ROD │──▶│ CASTING_BAIT │──▶│ WAITING_FOR_BITE│
   └──────────┘   └──────────────┘   └──────────────┘   └─────────────────┘
        ▲                ▲                                       │ (❗ bite)
        │                │                                       ▼
        │                │ (fish escaped)              ┌──────────────────┐
        │                └─────────────────────────────│ PLAYING_MINIGAME │
        │                                               └──────────────────┘
        │                                       (caught) │            │ (quick_finish)
        │                                                ▼            │
        │                                          ┌───────────┐      │
        └──────────────────────────────────────────│ FINISHING │◀─────┘ (esc → STARTING)
              (fishing-spot button reappears)       └───────────┘
                                                          │ ("Continue")
                                                          ▼  → CHECKING_ROD
```

**State-by-state behavior:**

- **`STARTING`** (`starting_state.py`) — Acquire the fishing UI.
  1. If a **server-connect** dialog is detected, click its confirm button (reconnect handling).
  2. If the **fishing-spot button** is found, press `F` to enter fishing → `CHECKING_ROD`.
  3. Else if a **level-check** marker is found, the player is already fishing → `CHECKING_ROD`.
  4. Else "wiggle" the character (`S`+`D` tap) every 2s to make the interact button reappear, and keep searching.

- **`CHECKING_ROD`** (`checking_rod_state.py`) — Ensure a usable rod.
  - Looks for any of `flex_rod` / `sturdy_rod` / `reg_rod` templates. If **none** match → rod is broken: increment `rod_breaks`, open menu (`M`), move+click a fixed equip slot `(1650, 580)` to equip a new rod. Always → `CASTING_BAIT`.

- **`CASTING_BAIT`** (`casting_bait_state.py`) — Cast the line.
  - Wait `casting_delay`, move mouse to screen center, click to ensure focus, then a quick left mouse press/release to cast → `WAITING_FOR_BITE`.

- **`WAITING_FOR_BITE`** (`waiting_for_bite_state.py`) — Watch for the bite cue.
  - Polls for the **exclamation (❗)** template. On hit: press-and-**hold** left mouse (begins reeling) → `PLAYING_MINIGAME`. Otherwise logs a "waiting" message at most every 5s.

- **`PLAYING_MINIGAME`** (`playing_minigame_state.py`) — Play the catch bar. *Core real-time algorithm:*
  - First check for end conditions: `success` template → `fish_caught++`; `failure` (fish escaped) → `fish_escaped++`.
  - On completion: release all controls; if `quick_finish_enabled`, press `ESC` → `STARTING`; else success → `FINISHING`, failure → `CHECKING_ROD`.
  - Otherwise, the **arrow-following controller** (`_handle_arrow`): if a `left_arrow`/`right_arrow` is on screen, hold the matching key (`A`/`D`); when the *opposite* arrow appears, release the previous key and re-evaluate, with a `switch_delay` (0.5 s) debounce. This continuously steers the catch indicator toward the target zone.

- **`FINISHING`** (`finishing_state.py`) — Confirm the catch.
  - If a **"Continue"** button appears, click it and increment `cycles` → `CHECKING_ROD` (next cast). If instead the fishing-spot button reappears (kicked out of UI) → `STARTING`.

---

## 6. Detection algorithm (`core/game/detector.py`)

This is the computer-vision heart of the bot.

1. **Template loading** — Each PNG in the template map is read with `IMREAD_UNCHANGED`. If it has an alpha channel (4 channels), the alpha is split off as a **transparency mask** and the color part converted to BGR; matching then ignores transparent pixels.
2. **Screen capture** — `mss` grabs the configured `monitor` region (BGRA) → NumPy array → converted to BGR. The `mss` instance is lazily created inside the bot thread.
3. **ROI restriction** — For a given template, look up its ROI `(x, y, w, h)` in `detection_config.rois` (ROIs may be a string alias pointing at another ROI). The search is clamped to screen bounds and limited to that small rectangle — drastically faster and less false-positive-prone than scanning the full frame.
4. **Matching** — Both the ROI crop and the template are grayscaled, then `cv.matchTemplate(..., cv.TM_CCOEFF_NORMED, mask=mask)`; `cv.minMaxLoc` extracts the best **confidence** (0–1) and its location. A match requires `confidence ≥ precision` (default `0.65`).
5. **Padded-ROI fallback (DS edition)** — If the ROI match fails and `radius > 0`, the detector retries **once** on a slightly padded ROI. This replaced the old concentric-square pixel sweep, which re-ran `matchTemplate` up to O(radius²) times per template each frame for results `matchTemplate` already covers.
6. **Resolution scaling (DS edition)** — Templates are resized once at load by the live scale factor, and ROIs are scaled per frame, so the same calibrated PNGs work at any resolution.
7. **Pre-computed grayscale (DS edition)** — Each template's grayscale (and alpha mask) is computed **once at load**, not per match; masked `TM_CCOEFF_NORMED` is used only when an alpha mask exists.
8. **Center calculation** — On a hit, `_calculate_center` returns the absolute on-screen `(x, y)` center of the matched template (adding ROI offset + monitor offset), ready to feed into mouse moves/clicks.

---

## 7. Guard rails / interceptors (`core/interceptors/`)

Cross-cutting safety checks that **run every frame before the active state**, inside `StateMachine.handle()`. Each extends the abstract `BaseInterceptor`. If an interceptor handles the frame, normal state handling is skipped for that tick. (In the original upstream these were never invoked and were internally broken — the DS edition wires and fixes them; see §14.)

- **`FocusGuardInterceptor` (DS edition)** — If the game isn't the foreground **process**, it **releases all controls and pauses input**. This prevents the bot's clicks from hitting other apps — notably the official launcher's *Play* button, which used to spawn a second game instance — and is the only guard rail run unconditionally.
- **State timeouts** act as the machine-level guard rail (see §4).

> The upstream `LevelCheckInterceptor` / `RodCheckInterceptor` were removed in the DS edition: the level-check guard looped forever on the normal fishing UI, and the rod-check one was never used.

---

## 8. Configuration (`config/`)

All tunables live here so behavior can change without touching logic.

- **`screen_config.py` → `ScreenConfig`** — Capture geometry. Scores all top-level windows to find the **real game client** (Unity `UnityWndClass` / title match) while **excluding the launcher** (Electron/CEF), reads the exact **client rect** (no title-bar guesswork), and computes the live-vs-reference **scale factors**. Honors `BPSR_WINDOW_TITLE` / `BPSR_WINDOW_CLASS` overrides. Exposes `is_game_foreground()`, `scale_point()`, `scale_rect()`.
- **`detection_config.py` → `DetectionConfig`** — The detection brain: `precision = 0.65`, the **template name → PNG file** map (15 templates), and the **ROI table** (FullHD-calibrated rectangles per template). Commented-out blocks document a slower "any resolution" mode (all ROIs `None`).
- **`bot_config.py` → `BotConfig`** — Behavior knobs: per-state `state_timeouts` (10–30 s), `quick_finish_enabled`, `debug_mode`, `target_fps` (0 = unlimited), and action delays (`default_delay`, `finish_wait_delay`, `casting_delay`).
- **`paths.py`** — Resolves `PACKAGE_ROOT`, `ASSETS_PATH`, `TEMPLATES_PATH` from the file location.
- **`__init__.py` → `Config`** — Aggregates the above and exposes `get_template_path(name)`.

---

## 9. Controls / hotkeys

| Key | Action |
|---|---|
| **7** | Toggle pause/resume (bot starts paused). |
| **8** | Stop the bot (prints stats, releases inputs, exits). |
| **9** | Toggle the transparent **ROI visualizer** overlay (runs in its own process). |

Input is simulated by **`GameController`** (`core/game/controller.py`): `press_key`, `click`/`click_at`, `move_to`, `mouse_down`/`mouse_up`, `key_down`/`key_up`, and `release_all_controls` (failsafe cleanup). PyAutoGUI `FAILSAFE` is on — slamming the mouse to a screen corner aborts.

---

## 10. Statistics (`core/stats.py`)

`StatsTracker` keeps session counters: `cycles`, `fish_caught`, `fish_escaped`, `rod_breaks`, `timeouts`. `increment()` bumps them during play; `show()` prints a formatted summary table on shutdown.

---

## 11. Complete file reference

### Root
| File | Purpose |
|---|---|
| `gui.py` | **Primary entry point** — launches the PyQt6 Demon Soul GUI (Doctor built in, F9/F10 hotkeys). See §15. |
| `main.py` | Console fallback. Enables DPI awareness, builds `FishingBot` + `Hotkeys`, runs the elevation advisory and the paused-aware update loop with a top-level safety net. |
| `doctor.py` | Console DEBUG DOCTOR — thin CLI over `src/fishbot/diagnostics.py` (DPI, elevation, window/launcher, capture region, per-template confidence, annotated screenshot). See §14. |
| `build.py` / `build.bat` | PyInstaller build of `Doctor.exe` and `BPSR-Fishing.exe` (templates bundled). |
| `run_as_admin.bat` | Relaunches the bot elevated (needed when the game runs as Administrator). |
| `requirements.txt` | Runtime dependencies (opencv-python, numpy, mss, PyAutoGUI, pydirectinput, keyboard, PyQt6). |
| `requirements-dev.txt` | Runtime deps + PyInstaller for building executables. |
| `README.md` / `README.pt-br.md` | User-facing guides (English / Brazilian Portuguese): features, install, run, troubleshooting, config, architecture. |
| `LICENSE` | GPL-3.0 license text. |
| `.gitignore` | Excludes Python/virtualenv/IDE/build artifacts from version control. |

### `src/fishbot/` (package)
| File | Purpose |
|---|---|
| `__init__.py` | Marks the package. |

### `src/fishbot/config/`
| File | Purpose |
|---|---|
| `__init__.py` | `Config` aggregator + `get_template_path`. |
| `screen_config.py` | `ScreenConfig`: capture region; auto-detects the game window (pywinctl), handles windowed-mode offsets. |
| `detection_config.py` | `DetectionConfig`: `precision`, template→file map, ROI rectangles. |
| `bot_config.py` | `BotConfig`: timeouts, FPS, delays, feature flags. |
| `paths.py` | Filesystem path constants (package/assets/templates). |

### `src/fishbot/core/`
| File | Purpose |
|---|---|
| `bot_component.py` | `BotComponent` base: injects `bot`, `config`, `detector`, `controller` into every component. |
| `fishing_bot.py` | `FishingBot`: top-level orchestrator; wires config, detector, controller, stats, interceptor, state machine; owns `start/update/stop`. |
| `stats.py` | `StatsTracker`: session counters + summary printout. |

### `src/fishbot/core/game/`
| File | Purpose |
|---|---|
| `detector.py` | `Detector`: `mss` capture + OpenCV template matching, ROI cropping, masked matching, concentric-square fallback, center calculation. |
| `controller.py` | `GameController`: PyAutoGUI keyboard/mouse simulation + `release_all_controls`. |
| `hotkeys.py` | `Hotkeys`: global `7/8/9` bindings; manages the ROI-visualizer subprocess. |

### `src/fishbot/core/state/`
| File | Purpose |
|---|---|
| `state_machine.py` | `StateMachine`: registry, transitions, per-state timeout enforcement + recovery. |
| `state_type.py` | `StateType` enum of the six states. |
| `bot_state.py` | `BotState` abstract base (adds interceptor + window access to `BotComponent`). |
| `impl/starting_state.py` | Acquire fishing UI; handle reconnect; press `F`; wiggle to surface the interact button. |
| `impl/checking_rod_state.py` | Verify/replace the rod via the menu. |
| `impl/casting_bait_state.py` | Focus + cast the line. |
| `impl/waiting_for_bite_state.py` | Detect the ❗ bite and start reeling. |
| `impl/playing_minigame_state.py` | Real-time arrow-following minigame controller; success/failure handling. |
| `impl/finishing_state.py` | Click "Continue"; count cycle; route back to fishing. |

### `src/fishbot/core/interceptors/`
| File | Purpose |
|---|---|
| `base_interceptor.py` | `BaseInterceptor` abstract guard-rail base. |
| `focus_guard_interceptor.py` | **(DS)** Pauses input when the game isn't the foreground **process** (fixes the launcher "second game" bug and false "not focused"). |

### `src/fishbot/utils/`
| File | Purpose |
|---|---|
| `logger.py` | `log()`: timestamped console logging; **reconfigures stdout/stderr to UTF-8** so emoji output never crashes a cp1252 console. |
| `winutil.py` | **(DS)** Win32/ctypes helpers: DPI awareness, admin/elevation checks, window enumeration, client-rect, foreground detection. |
| `roi_visualizer.py` | Optional PyQt6 transparent, click-through overlay drawing every ROI rectangle + label for calibration (lazily imported). |

### `src/fishbot/ui/`
| File | Purpose |
|---|---|
| `__init__.py` | Exposes `run()`; the GUI package. |
| `app.py` | **(DS)** PyQt6 GUI: status banner, Start/Stop, Doctor panel, stats, live log; runs diagnostics and the bot in worker threads (`DiagnosticsWorker`, `BotThread`); global F9/F10 hotkeys. |

### `src/fishbot/`
| File | Purpose |
|---|---|
| `diagnostics.py` | **(DS)** Shared Doctor logic → structured `DiagReport`, used by both the console Doctor and the GUI. |

### `src/fishbot/assets/templates/` — detection reference images (PNG)
| Template | Used to detect |
|---|---|
| `fishing_spot_btn.png` | The interact button at a fishing spot. |
| `connect.png` | Server reconnect/confirm dialog. |
| `level_check.png` | Marker proving the fishing UI is active. |
| `flex_pole.png`, `sturdy_pole.png`, `reg_pole.png` | Valid equipped-rod icons (flex / sturdy / regular). |
| `broken_rod.png` | Broken-rod indicator. |
| `new_rod.png` | Replacement rod in the equip menu. |
| `exclamation.png` | The ❗ bite cue. |
| `left_arrow.png`, `right_arrow.png` | Minigame direction prompts. |
| `success.png` | Fish-caught result. |
| `fish_escaped.png` | Fish-got-away result (`failure`). |
| `continue.png` | Post-catch "Continue" button. |

---

## 12. How to run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Launch the game at 1920x1080, stand at a fishing spot
# 3. Start the bot from the project root
python main.py

# 4. Press 7 to start/pause, 8 to stop, 9 to toggle the ROI overlay
```

**Tuning when detection breaks after a game patch:** replace the relevant PNG in `src/fishbot/assets/templates/`, and/or lower `precision` in `detection_config.py` (e.g. `0.65 → 0.55`). Use hotkey `9` to visually confirm ROIs line up with the on-screen elements.

---

## 13. About this fork (`-DS`)

This `BPSR-Fishing-Bot-DS` fork (owner `saptia14`) continues / customizes the unmaintained upstream (the "Demon Soul" edition). §14 documents the work done on top of the original architecture.

---

## 14. DS Edition — cross-machine robustness, resilience & efficiency

The DS edition targets one overarching goal: **run seamlessly on any Windows machine**, plus stronger resilience and lower CPU. Work was done in four phases.

### Bugs fixed

1. **"Detects nothing on a friend's PC."** Root causes were (a) the process was **not DPI-aware**, so on non-100% display scaling the window rect, captured pixels and click coordinates disagreed; (b) hard-coded 1920×1080 ROIs broke on other resolutions; (c) the window search matched a brittle `"Blue Protocol"` substring and **silently fell back** to wrong full-screen defaults. All three are addressed (DPI awareness, resolution scaling, robust client detection).
2. **Elevation mismatch.** If the game runs as Administrator but the bot doesn't, Windows (UIPI) silently drops the bot's input. The bot now **detects and warns** about this, and ships `run_as_admin.bat`.
3. **A second game instance launches via the launcher.** With no focus guard, the bot's center-click landed on the official launcher's *Play* button. Fixed by (a) attaching only to the real game client and **excluding launcher windows**, and (b) the **focus guard** that pauses input whenever the game isn't foreground.
4. **Dead/broken guard rails.** Upstream created `LevelCheckInterceptor` but never called it, and it referenced non-existent APIs (`bot.set_state`, string state keys, `_current_arrow`). Now interceptors **run every frame** and the level-check guard is corrected.
5. **Emoji crash on legacy consoles.** Emoji in logs raised `UnicodeEncodeError` on cp1252 consoles. Output is reconfigured to UTF-8 with replacement.

### Phase 1 — runs anywhere
- **DPI awareness** (`winutil.enable_dpi_awareness`, Per-Monitor-v2 with fallbacks), enabled before any capture in `main.py` / `doctor.py`.
- **Robust window acquisition** (`ScreenConfig`): scores candidates by class (`UnityWndClass`) and title, **excludes** launcher/Electron windows, reads the exact **client rect** (no `+32/+8` title-bar guesswork), and supports `BPSR_WINDOW_TITLE` / `BPSR_WINDOW_CLASS` overrides.
- **Elevation advisory** + `run_as_admin.bat`.
- **The Doctor** (`doctor.py`) — see below.

### Phase 2 — resilience
- Interceptors **wired into `StateMachine.handle()`** and run before the active state; per-interceptor exceptions are isolated.
- **`FocusGuardInterceptor`** — releases controls and pauses while the game isn't focused.
- **Fixed `LevelCheckInterceptor`** — uses `state_machine.set_state`, `StateType` keys, `_current_direction`.
- **Top-level safety net** — `FishingBot.update()` and the `main()` loop catch exceptions, always releasing controls so keys are never left held.
- **Detection-driven clicks** — rod replacement and reconnect now click the **detected template center** (with a resolution-scaled fallback) instead of hard-coded `(1650,580)`/`(1100,795)`.

### Phase 3 — portability across resolutions
- **Resolution-independent ROIs/templates** — ROIs are scaled per frame (`ScreenConfig.scale_rect`) and templates resized once at load to the live scale, so the 1920×1080 calibration works everywhere.
- **Scancode input** — `GameController` uses `pydirectinput` (hardware scancodes that DirectX/Unity games honor) with a PyAutoGUI fallback, and tracks held keys/buttons for a complete `release_all_controls`.

### Phase 4 — efficiency
- **Pre-computed grayscale templates** (was re-converting every match).
- **Padded-ROI fallback** replaces the O(radius²) concentric-square pixel sweep with a single retry.
- **Crop-then-grayscale** small ROIs instead of graying full frames; **masked matching only when a mask exists**; capture is limited to the game client region.

### The DEBUG DOCTOR (`doctor.py` → `Doctor.exe`)

A one-shot diagnostic that turns "it doesn't work" into a precise cause. It reports:
- Python/OS, **display scale**, **admin** state, and the active **input backend**.
- All **game-like windows** (title, class, pid, **elevation**, size) with the chosen one marked, and which window was excluded as the launcher.
- The exact **capture region** and **scale factor**, plus an **elevation-mismatch** and **focus** warning.
- A **live confidence** score for every detection template against the current screen.
- An annotated **`doctor_report.png`** with each ROI drawn green (match) / red (no match).
- A **summary** of likely problems.

### Building executables

`python build.py` (or `build.bat`) produces `dist/Doctor.exe` and `dist/BPSR-Fishing.exe` via PyInstaller (one-file, templates bundled, optional PyQt6 visualizer excluded). `paths.py` resolves bundled assets via `sys._MEIPASS` when frozen.

### New env-var overrides
| Variable | Effect |
|---|---|
| `BPSR_WINDOW_TITLE` | Regex to force-match the game window by title. |
| `BPSR_WINDOW_CLASS` | Regex to force-match the game window by class. |

---

## 15. The GUI (Demon Soul edition)

The primary entry point is now a **PyQt6 desktop app** (`gui.py` → `src/fishbot/ui/app.py`). It integrates the Doctor and the bot in one window — there is no separate Doctor.exe by default. The console `main.py` remains as a fallback.

### State flow
```
window opens → LOADING ──(DiagnosticsWorker)──▶ READY        (or ATTENTION if issues)
   F9 / Start ─▶ LOADING ──(BotThread warm-up)──▶ FISHING
   F10 / Stop ─▶ STOPPED ──▶ (start again / Re-run Doctor)
```
The status banner is colour-coded: LOADING (amber), READY (blue), ATTENTION (orange), FISHING (green), STOPPED (grey), ERROR (red).

### Threading model
- **`DiagnosticsWorker(QThread)`** runs `diagnostics.run_diagnostics()` off the UI thread and emits a `DiagReport`. The window populates the **Doctor** panel (window, region, scale, admin, elevation, focus, templates matched, issues) and moves to READY/ATTENTION.
- **`BotThread(QThread)`** constructs `FishingBot` (the LOADING/warm-up), then runs `bot.update()` in a loop, emitting status and live stats. `request_stop()` stops it cleanly; `mss` is created inside this thread, as required.
- **Logs** are mirrored into the on-screen console via `logger.subscribe(...)`, bridged to the GUI thread with a queued `pyqtSignal` so it's thread-safe.
- **Hotkeys** F9/F10 are registered globally with the `keyboard` library; their callbacks emit Qt signals (`hotkey_start`/`hotkey_stop`) so they cross safely into the UI thread. F9 = start/resume, F10 = stop.

### Why it's a single app
Per the brief, the Doctor is **built in**: the GUI runs the exact same `diagnostics.run_diagnostics()` during LOADING that the console Doctor uses, so a friend launches one `BPSR-Fishing.exe`, sees the diagnosis, and clicks Start. `build.py` defaults to building just this GUI exe (windowed, PyQt6 bundled); `build.py all` additionally produces the console `Doctor.exe` and `BPSR-Fishing-console.exe`.
