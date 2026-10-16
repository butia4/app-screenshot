"""Applies the size-cap policy to the app's own archives under one host directory."""

from collections.abc import Collection
from pathlib import Path

from app_screenshot.retention.policy import select_for_deletion
from app_screenshot.shared.layout import ARCHIVE_PATTERN, archive_sort_key
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
        self._over_cap = False  # an over-cap warning is already out for this episode

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
        """Best effort: an OSError on a single file is reported and skipped, never fatal."""
        try:
            archives = self._storage.list_files(self._host_dir, _ARCHIVES_GLOB)
        except OSError as exc:
            self._notifier.notify("warn", f"retention: cannot list archives: {exc}")
            return
        sized: list[tuple[Path, int]] = []
        for path in sorted(archives, key=archive_sort_key):
            try:
                sized.append((path, self._storage.size(path)))
            except OSError as exc:
                self._notifier.notify("warn", f"retention: cannot read size of {path.name}: {exc}")
        if not sized:
            self._over_cap = False
            return
        remaining = sum(size for _, size in sized)
        sizes = dict(sized)
        for path in select_for_deletion(sized, self._cap, protected):
            try:
                self._storage.delete(path)
            except OSError as exc:
                self._notifier.notify("warn", f"retention: could not delete {path.name}: {exc}")
                continue
            remaining -= sizes[path]
            self._notifier.notify("info", f"retention: deleted oldest archive {path.name}")
            self._prune(path)
        if remaining <= self._cap:
            self._over_cap = False
        elif not self._over_cap:
            self._over_cap = True
            self._notifier.notify(
                "warn", "newest or just-created archives alone exceed the size cap; keeping them"
            )

    def _prune(self, archive: Path) -> None:
        archives_dir = archive.parent
        session_dir = archives_dir.parent
        for d in (archives_dir, session_dir / "frames", session_dir, session_dir.parent):
            self._storage.remove_empty_dir(d)
