"""Effective configuration: defaults, size parsing and validation."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GIB = 1024**3
_UNITS = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}


class ConfigError(ValueError):
    """Invalid configuration; the message names the offending key."""


@dataclass(frozen=True)
class AppConfig:
    output_root: Path = Path.home() / "ScreenCaptures"
    capture_interval: float = 60.0
    archive_interval: float = 1800.0
    max_width: int = 1920
    quality: int = 75
    max_archive_size: int = 5 * GIB
    min_free_disk: int = 1 * GIB
    failure_limit: int = 10


KEYS = tuple(AppConfig.__dataclass_fields__)
MIN_WIDTH = 320


def parse_size(key: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ConfigError(f"{key}: expected a size like '5GB' or a byte count")
    if isinstance(value, int):
        number = value
    else:
        m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([A-Za-z]*)\s*", value)
        unit = m.group(2).upper() if m else ""
        if not m or (unit and unit not in _UNITS and unit + "B" not in _UNITS):
            raise ConfigError(f"{key}: cannot parse size {value!r} (use e.g. 500MB, 5GB)")
        unit = unit if unit in _UNITS else (unit + "B" if unit else "B")
        number = int(float(m.group(1)) * _UNITS[unit])
    if number < 0:
        raise ConfigError(f"{key}: must not be negative")
    return number


def _number(key: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{key}: expected a number")
    return float(value)


def _integer(key: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{key}: expected an integer")
    return value


def build_config(values: Mapping[str, Any]) -> AppConfig:
    """Validate raw values (only keys that were set) over the built-in defaults."""
    unknown = sorted(set(values) - set(KEYS))
    if unknown:
        raise ConfigError(f"unknown configuration key(s): {', '.join(unknown)}")
    base = AppConfig()
    out: dict[str, Any] = {}
    for key, raw in values.items():
        if key == "output_root":
            if not isinstance(raw, (str, Path)):
                raise ConfigError("output_root: expected a path string")
            out[key] = Path(raw).expanduser()
        elif key in ("capture_interval", "archive_interval"):
            out[key] = _number(key, raw)
        elif key in ("max_width", "quality", "failure_limit"):
            out[key] = _integer(key, raw)
        else:
            out[key] = parse_size(key, raw)
    cfg = AppConfig(**{**base.__dict__, **out})
    _validate(cfg)
    return cfg


def _validate(cfg: AppConfig) -> None:
    if cfg.capture_interval <= 0:
        raise ConfigError("capture_interval: must be > 0 seconds")
    if cfg.archive_interval <= 0:
        raise ConfigError("archive_interval: must be > 0 seconds")
    if cfg.archive_interval < cfg.capture_interval:
        raise ConfigError("archive_interval: must be >= capture_interval")
    if not 1 <= cfg.quality <= 100:
        raise ConfigError("quality: must be between 1 and 100")
    if cfg.max_width < MIN_WIDTH:
        raise ConfigError(f"max_width: must be >= {MIN_WIDTH}")
    if cfg.failure_limit < 1:
        raise ConfigError("failure_limit: must be >= 1")
    if cfg.max_archive_size <= 0:
        raise ConfigError("max_archive_size: must be > 0")
