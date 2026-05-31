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
| Input simulation | **PyAutoGUI 0.9.54** | Mouse move/click/hold and keyboard press/hold/release, with `FAILSAFE` enabled. |
| Global hotkeys | **`keyboard` 0.13.5** | System-wide `7`/`8`/`9` hotkeys to pause, stop, and toggle the ROI overlay. |
| Window discovery | **`pywinctl`** | Locates the "Blue Protocol: Star Resonance" window to auto-derive capture offsets (supports windowed mode). |
| Debug overlay GUI | **PyQt6 6.10 (+ `pyqt6-sip`)** | A transparent, click-through full-screen overlay (`roi_visualizer.py`) that draws every ROI rectangle for tuning. |
| Concurrency | **`multiprocessing`** (stdlib) | Runs the ROI visualizer in a separate process so it doesn't block the bot loop. |

> The game must run at **1920×1080**. Default ROIs are calibrated for FullHD; other resolutions require re-tuning the ROI table (or setting ROIs to `None` for a slower full-frame search).

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
5. **Concentric-square fallback search** — If the ROI match fails and a `radius > 0` was requested, `_generate_concentric_square_pixels` yields pixel coordinates on the perimeters of ever-larger squares around the ROI origin, re-running the match at each shifted offset. This tolerates small UI drift without paying for a full-frame scan.
6. **Center calculation** — On a hit, `_calculate_center` returns the absolute on-screen `(x, y)` center of the matched template (adding ROI offset + monitor offset), ready to feed into mouse moves/clicks.

---

## 7. Guard rails / interceptors (`core/interceptors/`)

Cross-cutting safety checks that can fire regardless of state, all extending the abstract `BaseInterceptor` (which itself uses the shared `BotComponent` to get `bot`, `config`, `detector`, `controller`).

- **`LevelCheckInterceptor`** — If the "level check" UI is detected, release controls, clear any in-progress minigame direction, and reset to `CHECKING_ROD`. (Wired into `FishingBot` and available to every state via `BotState`.)
- **`RodCheckInterceptor`** — If a broken-rod indicator is detected, release controls and signal a rod problem. (Provided as a reusable guard rail.)
- **State timeouts** act as the machine-level guard rail (see §4).

---

## 8. Configuration (`config/`)

All tunables live here so behavior can change without touching logic.

- **`screen_config.py` → `ScreenConfig`** — Capture geometry. Defaults to `1920×1080` at `(0,0)`; uses **`pywinctl`** to find the "Blue Protocol" window and auto-adjust offsets for **windowed mode** (accounting for the title bar / borders).
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
| `main.py` | Entry point. Builds `FishingBot` + `Hotkeys`, prints the start banner, runs the paused-aware update loop until stopped. |
| `requirements.txt` | Python dependencies (PyQt6, pywinctl, opencv-python, mss, PyAutoGUI, keyboard). |
| `README.md` / `README.pt-br.md` | User-facing guides (English / Brazilian Portuguese): features, install, run, troubleshooting, config, architecture. |
| `LICENSE` | GPL-3.0 license text. |
| `.gitignore` | Excludes Python/virtualenv/IDE artifacts from version control. |

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
| `level_check_interceptor.py` | Detects level-check UI → reset to `CHECKING_ROD`. |
| `rod_check_interceptor.py` | Detects broken-rod indicator → release controls. |

### `src/fishbot/utils/`
| File | Purpose |
|---|---|
| `logger.py` | `log()`: timestamped console logging used throughout. |
| `roi_visualizer.py` | PyQt6 transparent, click-through full-screen overlay drawing every ROI rectangle + label for calibration. |

### `src/fishbot/ui/`
| File | Purpose |
|---|---|
| `__init__.py` | Placeholder reserved for a future configuration GUI. |

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

This `BPSR-Fishing-Bot-DS` fork (owner `saptia14`) preserves the upstream architecture verbatim as a starting point. The upstream project is no longer maintained by its original author; this fork exists to continue / customize it (the "Demon Soul" edition). Suggested next steps mirror the upstream roadmap: a configuration **GUI** (the reserved `ui/` package), broader **resolution support**, and improved **resilience** to unexpected in-game events.
