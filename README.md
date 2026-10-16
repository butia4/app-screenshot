# app-screenshot

Unattended, periodic desktop screen capture. Every capture is kept: frames are saved as
WebP (JPEG fallback), bundled into verified uncompressed zip archives, and the only thing
ever deleted is the oldest archive once the total archive size exceeds the cap.

## Privacy and consent

This tool records everything visible on your screen (all monitors) at a fixed interval.
Only run it on machines where the people using them know and consent to this. A console
banner announcing the recording is printed at startup and the process runs in a visible
console window. Captured data may contain passwords, messages and personal information:
protect the output directory accordingly.

## Install

Requires Python 3.11+.

    python3 -m venv .venv
    . .venv/bin/activate
    pip install -e ".[dev]"

## Usage

    app-screenshot                      # defaults
    app-screenshot --interval 30 --output /data/captures
    app-screenshot --config app-screenshot.toml
    python -m app_screenshot --help

Stop with Ctrl+C (or SIGTERM). Pending frames are archived before exit; a second signal
exits immediately and the next start recovers any leftovers.

Exit codes: 0 ok, 1 unexpected error or too many consecutive capture failures,
2 invalid configuration, 3 unsupported platform.

## Configuration

Precedence per key: CLI flag > TOML file > built-in default. The TOML file is given with
`--config PATH`; otherwise `app-screenshot.toml` is read from the current directory (or
beside the executable in a frozen build) if present. Unknown keys are an error.

| TOML key            | CLI flag               | Default            | Notes                              |
|---------------------|------------------------|--------------------|------------------------------------|
| `output_root`       | `--output`             | `~/ScreenCaptures` | `<root>/<host>/<date>/session-*`   |
| `capture_interval`  | `--interval`           | `60`               | seconds                            |
| `archive_interval`  | `--archive-interval`   | `1800`             | seconds, >= capture_interval       |
| `max_width`         | `--max-width`          | `1920`             | no upscaling, >= 320               |
| `quality`           | `--quality`            | `75`               | 1-100                              |
| `max_archive_size`  | `--max-archive-size`   | `5GB`              | oldest archives deleted first      |
| `min_free_disk`     | `--min-free-disk`      | `1GB`              | capture pauses below, resumes +10% |
| `failure_limit`     | `--failure-limit`      | `10`               | consecutive capture failures before exit 1, >= 1 |

Sizes accept `B`, `KB`, `MB`, `GB`, `TB` (1024-based).

## Platform notes

- Linux: X11 only. Wayland sessions, and sessions with `DISPLAY` unset, exit with code 3 and
  a message.
- macOS: grant Screen Recording permission to the terminal (or packaged app) in System
  Settings > Privacy & Security. Without it frames come out blank; the app warns after
  three consecutive uniform frames but still saves them.
- Windows: run from a console window; DPI awareness is set by `mss`.

## Retention and archive scope

- Retention only considers archives under the current host directory
  (`<root>/<host>/`), not the whole output root; other hosts' captures are never touched.
- An archive created in the current pass (including archives made by startup recovery of
  older sessions) is never deleted by that pass's retention, even if the total stays over
  the cap. Otherwise the oldest archives (by date/session path) go first.
- A wall-clock gap is detected when the wall clock advances more than 2x the capture
  interval beyond the monotonic clock, or more than 3x the interval in total (suspend/resume);
  missed ticks are skipped and a warning is printed.
- Blank-frame warning: after 3 consecutive uniform frames, at most once per 600 s. Frames are
  always saved regardless.

## Packaging

    pyinstaller packaging/app-screenshot.spec

Produces a onedir build (`dist/app-screenshot/`) with a console window.

## Development

    ruff check . && ruff format --check . && pytest

The core depends on ports (capturer, encoder, archiver, clock, storage, notifier), so the
suite runs headless with fakes. The `mss` adapter needs a display and is validated manually.

## Manual validation checklist

- [ ] macOS: Screen Recording permission is attributed to the terminal / packaged app
- [ ] Frozen build runs and the `mss` hidden imports resolve on each OS
- [ ] Real frame sizes versus the archive cap on a multi-monitor setup
- [ ] WebP available in Pillow wheels per OS; JPEG fallback path works
- [ ] Windows console close, then recovery on next start
- [ ] Tune the blank-frame stddev threshold (2.0) on real screens
- [ ] Windows DPI correctness and Linux X11 multi-monitor
