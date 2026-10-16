"""Free-disk guard with hysteresis: pauses capture, never discards anything."""

from pathlib import Path

from app_screenshot.shared.notifier import Notifier
from app_screenshot.shared.storage import Storage

HYSTERESIS = 1.1


class DiskGuard:
    def __init__(self, storage: Storage, notifier: Notifier, root: Path, min_free: int) -> None:
        self._storage = storage
        self._notifier = notifier
        self._root = root
        self._min_free = min_free
        self._paused = False
        self._warned_unknown = False

    @property
    def paused(self) -> bool:
        return self._paused

    def ok(self) -> bool:
        """True when capturing is allowed. Notifies once per pause/resume transition."""
        try:
            free = self._storage.free_bytes(self._root)
        except OSError as exc:
            if not self._warned_unknown:
                self._warned_unknown = True
                self._notifier.notify(
                    "warn", f"cannot determine free disk space ({exc}); continuing"
                )
            return not self._paused
        if self._paused:
            if free >= self._min_free * HYSTERESIS:
                self._paused = False
                self._notifier.notify("info", "free disk space recovered; capture resumed")
        elif free < self._min_free:
            self._paused = True
            self._notifier.notify(
                "warn", f"free disk space below {self._min_free // 2**20} MiB; capture paused"
            )
        return not self._paused
