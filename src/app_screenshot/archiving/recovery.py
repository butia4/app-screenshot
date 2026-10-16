"""Startup recovery: drop leftover temp files and archive frames of dead sessions."""

from pathlib import Path

from app_screenshot.archiving.ports import Archiver
from app_screenshot.archiving.service import ArchiveService, list_frames
from app_screenshot.shared.notifier import Notifier
from app_screenshot.shared.storage import Storage


class Recovery:
    def __init__(
        self, storage: Storage, archiver: Archiver, service: ArchiveService, notifier: Notifier
    ) -> None:
        self._storage = storage
        self._archiver = archiver
        self._service = service
        self._notifier = notifier

    def run(self, host_dir: Path) -> None:
        for pattern in ("*/session-*/archives/*.tmp", "*/session-*/frames/*.tmp"):
            for leftover in self._storage.list_files(host_dir, pattern):
                try:
                    self._storage.delete(leftover)
                except OSError as exc:
                    self._notifier.notify(
                        "warn", f"recovery: could not remove leftover {leftover.name}: {exc}"
                    )
                    continue
                self._notifier.notify("info", f"recovery: removed leftover {leftover.name}")
        sessions = sorted(
            {p.parent.parent for p in self._storage.list_files(host_dir, "*/session-*/frames/*")}
        )
        for session in sessions:
            frames_dir, archives_dir = session / "frames", session / "archives"
            self._drop_already_archived(frames_dir, archives_dir)
            self._service.archive(frames_dir, archives_dir)

    def _drop_already_archived(self, frames_dir: Path, archives_dir: Path) -> None:
        """Crash between replace and delete: delete only frames whose size and CRC32 match."""
        for zip_path in self._storage.list_files(archives_dir, "*.zip"):
            try:
                index = self._archiver.read_index(zip_path)
                loose = {f.name: f for f in list_frames(self._storage, frames_dir)}
            except Exception as exc:
                if isinstance(exc, OSError):
                    self._notifier.notify(
                        "warn", f"recovery: cannot inspect {zip_path.name}: {exc}"
                    )
                continue
            covered = {n: loose[n] for n in index if n in loose}
            if not covered:
                continue
            matched = self._archiver.matching(zip_path, covered)
            for name in sorted(set(covered) - matched):
                self._notifier.notify(
                    "warn", f"recovery: {name} differs from the copy in {zip_path.name}; keeping it"
                )
            removed = 0
            for name in sorted(matched):
                try:
                    self._storage.delete(covered[name])
                except OSError as exc:
                    self._notifier.notify("warn", f"recovery: could not delete {name}: {exc}")
                    continue
                removed += 1
            if removed:
                self._notifier.notify(
                    "info", f"recovery: removed {removed} frames already in {zip_path.name}"
                )
