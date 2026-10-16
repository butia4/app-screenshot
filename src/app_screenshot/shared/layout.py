"""Output path naming: <root>/<host>/<YYYY-MM-DD>/session-<HHMMSS>/{frames,archives}."""

import re
import socket
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

FRAME_PATTERNS = ("*.webp", "*.jpg")
ARCHIVE_PATTERN = "*.zip"


def sanitize_hostname(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return cleaned or "host"


def current_hostname() -> str:
    return sanitize_hostname(socket.gethostname())


@dataclass(frozen=True)
class SessionLayout:
    root: Path
    hostname: str
    started: datetime

    @property
    def host_dir(self) -> Path:
        return self.root / self.hostname

    @property
    def session_dir(self) -> Path:
        return (
            self.host_dir
            / self.started.strftime("%Y-%m-%d")
            / f"session-{self.started.strftime('%H%M%S')}"
        )

    @property
    def frames_dir(self) -> Path:
        return self.session_dir / "frames"

    @property
    def archives_dir(self) -> Path:
        return self.session_dir / "archives"

    def frame_name(self, when: datetime, seq: int, ext: str) -> str:
        return f"{when.strftime('%Y%m%dT%H%M%S')}-{seq:05d}.{ext}"
