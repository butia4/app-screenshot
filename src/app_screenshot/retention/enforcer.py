"""Applies the size-cap policy to the app's own archives under one host directory."""

from collections.abc import Collection
from pathlib import Path

from app_screenshot.retention.policy import select_for_deletion
from app_screenshot.shared.layout import ARCHIVE_PATTERN
from app_screenshot.shared.notifier import Notifier
from app_screenshot.shared.storage import Storage

# <date>/<session>/archives/*.zip relative to the host directory
_ARCHIVES_GLOB = f"*/session-*/archives/{ARCHIVE_PATTERN}"


class RetentionEnforcer:
    def __init__(self, storage: Storage, notifier: Notifier, host_dir: Path, cap: int) -> None:
        self._storage = storage
        self._notifier = notifier
        self._host_dir = host_dir
        self._cap = cap
        self._startup: list[Path] | None = None

    def begin_startup(self) -> None:
        """Start of startup recovery: every archive produced until `end_startup` is protected."""
        self._startup = []

    def end_startup(self) -> None:
        held, self._startup = self._startup or [], None
        self.enforce(held)

    def on_archive(self, created: Path) -> None:
        """ArchiveService hook: enforce the cap, never deleting what this pass just created."""
        if self._startup is not None:
            self._startup.append(created)
            self.enforce(self._startup)
        else:
            self.enforce([created])

    def enforce(self, protected: Collection[Path] = ()) -> None:
        archives = self._storage.list_files(self._host_dir, _ARCHIVES_GLOB)
        sized = [(p, self._storage.size(p)) for p in archives]
        if not sized:
            return
        remaining = sum(size for _, size in sized)
        sizes = dict(sized)
        for path in select_for_deletion(sized, self._cap, protected):
            self._storage.delete(path)
            remaining -= sizes[path]
            self._notifier.notify("info", f"retention: deleted oldest archive {path.name}")
            self._prune(path)
        if remaining > self._cap:
            self._notifier.notify(
                "warn", "newest or just-created archives alone exceed the size cap; keeping them"
            )

    def _prune(self, archive: Path) -> None:
        archives_dir = archive.parent
        session_dir = archives_dir.parent
        for d in (archives_dir, session_dir / "frames", session_dir, session_dir.parent):
            self._storage.remove_empty_dir(d)
