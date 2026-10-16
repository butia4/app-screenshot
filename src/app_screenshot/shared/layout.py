"""Output path naming: <root>/<host>/<YYYY-MM-DD>/session-<HHMMSS>/{frames,archives}."""

import re
import socket
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

FRAME_PATTERNS = ("*.webp", "*.jpg")
ARCHIVE_PATTERN = "*.zip"

_ARCHIVE_SEQ = re.compile(r"^(\d+)_")
_FRAME_SEQ = re.compile(r"-(\d+)\.(?:webp|jpg)$")
_SESSION_KEY = re.compile(r"^session-(\d{6})(?:-(\d+))?$")


def archive_seq(name: str) -> int | None:
    """Numeric sequence of an archive name (any digit count), or None if it has none."""
    m = _ARCHIVE_SEQ.match(name)
    return int(m.group(1)) if m else None


def frame_seq(name: str) -> int | None:
    """Numeric sequence of a frame name, or None if it does not follow the naming scheme."""
    m = _FRAME_SEQ.search(name)
    return int(m.group(1)) if m else None


def session_key(name: str) -> tuple[str, int]:
    """Sort key of a session dir name: (HHMMSS, collision suffix; 1 when absent)."""
    m = _SESSION_KEY.match(name)
    if not m:
        return (name, 0)
    return (m.group(1), int(m.group(2)) if m.group(2) else 1)


def archive_sort_key(path: Path) -> tuple[str, tuple[str, int], int, str]:
    """Oldest-first key for <...>/<date>/<session>/archives/<name>: numeric, not textual."""
    seq = archive_seq(path.name)
    return (
        path.parent.parent.parent.name,
        session_key(path.parent.parent.name),
        -1 if seq is None else seq,
        path.name,
    )


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
    suffix: int = 1  # >= 2 when the session dir of the same start second already existed

    @classmethod
    def allocate(
        cls,
        root: Path,
        hostname: str,
        started: datetime,
        exists: Callable[[Path], bool],
    ) -> "SessionLayout":
        """First layout whose session dir does not exist yet (`session-HHMMSS[-N]`, N >= 2)."""
        layout = cls(root, hostname, started)
        n = 1
        while exists(layout.session_dir):
            n += 1
            layout = cls(root, hostname, started, n)
        return layout

    @property
    def host_dir(self) -> Path:
        return self.root / self.hostname

    @property
    def session_dir(self) -> Path:
        return (
            self.host_dir
            / self.started.strftime("%Y-%m-%d")
            / f"session-{self.started.strftime('%H%M%S')}{self._suffix}"
        )

    @property
    def _suffix(self) -> str:
        return f"-{self.suffix}" if self.suffix > 1 else ""

    @property
    def frames_dir(self) -> Path:
        return self.session_dir / "frames"

    @property
    def archives_dir(self) -> Path:
        return self.session_dir / "archives"

    def frame_name(self, when: datetime, seq: int, ext: str) -> str:
        return f"{when.strftime('%Y%m%dT%H%M%S')}-{seq:05d}.{ext}"
