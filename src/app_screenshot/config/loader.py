"""Configuration merge: CLI flags > TOML file > built-in defaults."""

import argparse
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app_screenshot.config.settings import AppConfig, ConfigError, build_config

DEFAULT_CONFIG_NAME = "app-screenshot.toml"

_FLAGS: tuple[tuple[str, str, type | None, str], ...] = (
    ("--output", "output_root", str, "output root directory"),
    ("--interval", "capture_interval", float, "seconds between captures (default 60)"),
    ("--archive-interval", "archive_interval", float, "seconds between archives (default 1800)"),
    ("--max-width", "max_width", int, "downscale frames wider than this (default 1920)"),
    ("--quality", "quality", int, "encoder quality 1-100 (default 75)"),
    ("--max-archive-size", "max_archive_size", str, "archive size cap, e.g. 5GB"),
    (
        "--failure-limit",
        "failure_limit",
        int,
        "consecutive capture failures before exit (default 10)",
    ),
    ("--min-free-disk", "min_free_disk", str, "pause capture below this free space, e.g. 1GB"),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app-screenshot",
        description="Periodic desktop screen capture with verified zip archiving.",
    )
    parser.add_argument("--config", metavar="PATH", default=argparse.SUPPRESS, help="TOML file")
    for flag, dest, typ, help_text in _FLAGS:
        parser.add_argument(flag, dest=dest, type=typ, default=argparse.SUPPRESS, help=help_text)
    return parser


def _find_default_config() -> Path | None:
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    candidate = base / DEFAULT_CONFIG_NAME
    return candidate if candidate.is_file() else None


def _read_toml(path: Path, *, explicit: bool) -> dict[str, Any]:
    if not path.is_file():
        if explicit:
            raise ConfigError(f"config file not found: {path}")
        return {}
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: malformed TOML ({exc})") from exc


def load_config(argv: Sequence[str] | None = None) -> AppConfig:
    """Raises ConfigError on bad input; argparse errors exit with code 2."""
    args = vars(build_parser().parse_args(argv))
    config_path = args.pop("config", None)
    if config_path is not None:
        file_values = _read_toml(Path(config_path), explicit=True)
    else:
        default = _find_default_config()
        file_values = _read_toml(default, explicit=False) if default else {}
    return build_config({**file_values, **args})
