<p align="right">
  <a href="./README.md">English</a> |
  <a href="./README.pt-BR.md">Português (Brasil)</a>
</p>

<p align="left">
    <a href="#"><img alt="Build Status" src="https://github.com/your-username/BPSR-Fishing-Bot/actions/workflows/main.yml/badge.svg"></a>
    <a href="#"><img alt="Project Version" src="https://img.shields.io/badge/version-1.0.0-blue"></a>
    <a href="./LICENSE"><img alt="License" src="https://img.shields.io/badge/license-GPL--3.0-brightgreen"></a>
    <a href="https://www.python.org"><img alt="Python" src="https://img.shields.io/badge/Python-3.8+-3776AB?logo=python"></a>
    <a href="https://opencv.org"><img alt="OpenCV" src="https://img.shields.io/badge/OpenCV-4.x-5C3EE8?logo=opencv"></a>
</p>

# BPSR Fishing Bot

## This Project will not be updated by me anymore
### The Reason is Simple, i'm no longer active on Blue Protocol. tks u all

An automated and open-source fishing bot built in Python. It uses image detection to identify on-screen events and interact with a game's fishing minigame, automating the entire process.

---

## Table of Contents

*   [Features](#features)
*   [Quick Start Guide](#quick-start-guide)
    *   [Prerequisites](#1-prerequisites)
    *   [Installation](#2-installation)
    *   [How to Run](#3-how-to-run)
*   [Known Issues and Solutions](#known-issues-and-solutions)
*   [Configuration](#configuration)
*   [For Developers](#for-developers)
    *   [Architecture](#architecture)
    *   [Project Structure](#project-structure)
*   [Future Plans](#future-plans)

---

## Features

*   **Fully Automated Fishing:** Casts the line, detects a bite, and starts the minigame.
*   **Smart Minigame Player:** Autonomously plays the fishing minigame, moving left and right as needed.
*   **Automatic Rod Swapping:** Detects when the fishing rod breaks and replaces it with a new one, allowing for uninterrupted fishing sessions.
*   **Hotkey Control:** Easily start, pause, resume, and stop the bot using hotkeys ('7' and '8' keys).
*   **Flexible Configuration:** Allows for easy adjustment of detection precision, regions of interest (ROI), and wait times through dedicated configuration files.
*   **Robust Architecture:** Built with a state machine and solid design principles, making the code easy to understand and extend.

---

## Quick Start Guide

### 1. Prerequisites

*   **Python 3.8+**
*   The game running on screen. **Any resolution** works — detection ROIs and templates are auto-scaled from the 1920×1080 reference to your actual window size. Windowed or full-screen, primary or secondary monitor, and non-100% display scaling are all handled automatically.

### 2. Installation

1.  Clone this repository:
    ```bash
    git clone https://github.com/your-username/BPSR-Fishing-Bot.git
    cd BPSR-Fishing-Bot
    ```

2.  Install the dependencies from `requirements.txt`:
    ```bash
    pip install -r requirements.txt
    ```

### 3. How to Run

1.  Open the game and make sure it is visible on the screen.
2.  Be at a fishing location. Either stand on an interactable fishing spot or already in the fishing UI.
3.  Run the bot from the project's root folder:
    ```bash
    python main.py
    ```
4.  The bot will be ready. Press **7** key to start/pause, **8** to stop, and **9** to toggle the ROI visualizer. Keep the **game window focused** — the bot pauses its input whenever the game is not the active window (this protects the official launcher from accidental clicks).

> **Run as Administrator if the game is elevated.** If the game runs with admin rights but the bot does not, Windows silently ignores the bot's keystrokes/clicks. Use `run_as_admin.bat` (or right-click → *Run as administrator*). The bot prints a warning when it detects this mismatch.

### Diagnose problems with the Doctor

If the bot doesn't seem to detect anything on a given machine, run the **Doctor** first:

```bash
python doctor.py
```

It reports your display scaling, admin/elevation state, the detected game window vs. the launcher, the exact capture region, and a live confidence score for every detection template — and saves an annotated `doctor_report.png`. This turns "it doesn't work" into a precise diagnosis.

### Standalone executables (no Python needed)

Build self-contained `.exe` files for sharing with friends:

```bash
python build.py          # builds dist\Doctor.exe and dist\BPSR-Fishing.exe
```

`Doctor.exe` is the diagnostic tool; `BPSR-Fishing.exe` is the bot. Detection templates are bundled inside each executable.

---

## Known Issues and Solutions

This section lists common issues you might encounter and how to solve them.

### The detection of an item (e.g., broken rod, fish bite) stops working

*   **Symptom:** The bot stops reacting to a specific event that used to work, such as not swapping a broken rod or not detecting a bite.
*   **Likely Cause:** The game may have received a minor visual update, changing the appearance of the icon or image the bot is looking for.
*   **Solution:**
    1.  **Take a new screenshot** of the failed image (e.g., the broken rod icon).
    2.  **Replace the corresponding template file** in the `src/fishbot/assets/templates/` folder.
    3.  If the problem persists, try **adjusting the `precision` value** in the `src/fishbot/config/detection_config.py` file. Lowering the value (e.g., from `0.8` to `0.7`) can help compensate for minor visual differences.

### The bot detects nothing / does nothing on another PC

*   **Symptom:** Installed and configured correctly, game open and given admin rights, but the bot reacts to nothing.
*   **Likely Causes & Fixes:**
    1.  **Run the Doctor** (`python doctor.py` or `Doctor.exe`) — it pinpoints the cause.
    2.  **Elevation mismatch:** the game runs as Administrator but the bot doesn't, so Windows silently drops the bot's input. Run the bot as administrator (`run_as_admin.bat`).
    3.  **Display scaling:** handled automatically now (the process is DPI-aware), but verify the annotated `doctor_report.png` lines up with the game.
    4.  **Wrong window:** the bot attaches to the *game client*, never the launcher. If detection fails, set `BPSR_WINDOW_TITLE` (a regex) to force-match your game window.

### A second copy of the game launches when I start the bot

*   **Symptom:** Running the bot opens another instance of the game, even though it was already open via the official launcher.
*   **Cause:** With the launcher window focused, the bot's simulated clicks landed on the launcher's **Play** button.
*   **Fix (built-in):** The bot now (a) attaches only to the real game client and explicitly excludes the launcher, and (b) **pauses all input whenever the game window isn't focused**. Keep the game as the active window while the bot runs.

### Character won't resume fishing after a timeout state

*   **Symptom:** Something unexpected occurred (like fish escaped) and the bot has escaped the fishing UI and won't start again.
*   **Cause:** When the bot escapes it tries to re-enter the fishing UI by interacting with the fishing spot. Because some spots move the player after interacting with the fishing spot, the bot idly tries to interact when nothing is there. Bot also does not support a search to find the nearest one.
*   **Solution:** Move your character over to an interactable fishing spot to resume the bot.

---

## Configuration

The bot's behavior can be adjusted through the files located in `src/fishbot/config/`.

#### `screen_config.py`
Defines the screen capture area.
*   `monitor_width`, `monitor_height`: The game's screen resolution (default: 1920x1080).
*   `monitor_x`, `monitor_y`: Coordinates of the top-left corner of the monitor where the game is running. For the primary monitor, keep this as `(0, 0)`.

#### `detection_config.py`
Controls image detection.
*   `precision`: The minimum confidence (from `0.0` to `1.0`) for a template to be considered a match.
*   `templates`: Maps event names to their corresponding image files in `src/fishbot/assets/templates/`.
*   `rois` (Regions of Interest): Defines rectangles `(x, y, width, height)` to limit the search area for each template, increasing performance and accuracy.

#### `bot_config.py`
General bot settings.
*   `state_timeouts`: Maximum time the bot can remain in each state before resetting.
*   `target_fps`: Target frames per second for screen captures (0 for unlimited).
*   `default_delay`: Default delays between actions.
*   `casting_delay`: Delay right before casting a bait. 

---

## For Developers

### Architecture

The bot uses a **Finite State Machine (FSM)** to manage its workflow. The logic is divided as follows:

*   **`main.py`**: The entry point that initializes and runs the bot.
*   **`src/fishbot/core/state/`**: Contains the state machine logic.
    *   `state_machine.py`: Manages the current state and transitions.
    *   `impl/`: Houses the classes for each concrete state (`CheckingRodState`, `PlayingMinigameState`, etc.), where each implements a single responsibility.
*   **`src/fishbot/core/game/`**: Modules that interact directly with the game.
    *   `detector.py`: Responsible for screen capture and template detection using `mss` and `OpenCV`.
    *   `controller.py`: Simulates keyboard and mouse inputs.
*   **`src/fishbot/utils/`**: Utility modules, such as the logger function.

### Project Structure

```
BPSR-Fishing-Bot/
├── src/
│   └── fishbot/
│       ├── assets/         # Images (templates) for detection
│       ├── config/         # Bot configuration files
│       ├── core/
│       │   ├── game/       # Game interaction modules (Detector, Controller)
│       │   └── state/      # State Machine Logic
│       ├── ui/             # (Reserved for a future GUI)
│       └── utils/          # Utility modules
├── .gitignore
├── main.py                 # Application entry point
├── README.md
└── requirements.txt
```

## Future Plans

*   [ ] Graphical user interface (GUI) for easier configuration.
*   [x] Hotkey system to start/stop the bot.
*   [x] Improve resilience to unexpected in-game events. *(DS: guard rails wired + fixed, focus guard, exception safety net, detection-driven clicks.)*
*   [x] Run seamlessly on any Windows machine. *(DS: DPI awareness, resolution-independent ROIs/templates, robust game-vs-launcher detection, elevation handling.)*
*   [x] Standalone executables + a DEBUG DOCTOR diagnostic tool.

---

Feel free to open an *issue* or submit a *pull request*!