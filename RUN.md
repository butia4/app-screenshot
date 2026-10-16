# Running app-screenshot

Quick reference for setting up, running, testing and packaging the project. For the full
behavior (config keys, retention rules, platform notes) see `README.md`.

## 1. Prerequisites

- Python 3.11+
- A graphical session to capture:
  - Linux: X11 (`DISPLAY` set). Wayland or no display exits with code 3.
  - macOS: Screen Recording permission for the terminal or packaged app.
  - Windows: run from a console window.

## 2. Set up the environment

Linux / macOS:

    python3 -m venv .venv
    . .venv/bin/activate
    pip install -e ".[dev]"

Windows (PowerShell):

    py -3.11 -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -e ".[dev]"

## 3. Run

    app-screenshot --help                                  # list all flags
    app-screenshot                                         # defaults: every 60 s into ./ScreenCaptures
    app-screenshot --interval 30 --output /data/captures   # custom interval and output dir
    app-screenshot --config app-screenshot.toml            # load settings from TOML
    python -m app_screenshot                               # same, without the console script

Stop with `Ctrl+C` (or `SIGTERM`). Pending frames are archived before exit; a second signal
exits immediately and the next start recovers leftovers.

Output lands in `<output>/<host>/<YYYY-MM-DD>/session-<HHMMSS>/{frames,archives}`. For
unattended/scheduled runs, use an absolute `--output` path.

### Example config file

`app-screenshot.toml` (read from the current directory if `--config` is not given):

    output_root = "/data/captures"
    capture_interval = 60
    archive_interval = 1800
    max_width = 1920
    quality = 75
    max_archive_size = "5GB"
    min_free_disk = "1GB"
    failure_limit = 10

Precedence: CLI flag > TOML > default. Unknown keys exit with code 2.

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | OK (including stop during startup recovery) |
| 1 | Unexpected error or too many consecutive capture/save failures |
| 2 | Invalid configuration |
| 3 | Unsupported platform |

## 4. Test and lint

    ruff check . && ruff format --check . && pytest       # full check
    pytest tests/archiving/test_service.py::test_name     # single test
    ruff format .                                         # apply formatting

The test suite is headless (uses fakes); no display needed.

## 5. Package a standalone build

    pyinstaller packaging/app-screenshot.spec

Produces a onedir build in `dist/app-screenshot/`. Run the executable inside it; an
`app-screenshot.toml` placed beside the executable is picked up automatically.
