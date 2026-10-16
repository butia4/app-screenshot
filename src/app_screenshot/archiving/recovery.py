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
                self._storage.delete(leftover)
                self._notifier.notify("info", f"recovery: removed leftover {leftover.name}")
        sessions = sorted(
            {p.parent.parent for p in self._storage.list_files(host_dir, "*/session-*/frames/*")}
        )
        for session in sessions:
            frames_dir, archives_dir = session / "frames", session / "archives"
            self._drop_already_archived(frames_dir, archives_dir)
            self._service.archive(frames_dir, archives_dir)

    def _drop_already_archived(self, frames_dir: Path, archives_dir: Path) -> None:
        """Crash between replace and delete: re-verify the zip, then delete its originals."""
        for zip_path in self._storage.list_files(archives_dir, "*.zip"):
            try:
                index = self._archiver.read_index(zip_path)
            except Exception:
                continue
            loose = {f.name: f for f in list_frames(self._storage, frames_dir)}
            covered = {n: loose[n] for n in index if n in loose}
            if not covered:
                continue
            if not self._archiver.verify(zip_path, index):
                continue
            if all(self._storage.size(f) == index[n] for n, f in covered.items()):
                for frame in covered.values():
                    self._storage.delete(frame)
                self._notifier.notify(
                    "info", f"recovery: removed {len(covered)} frames already in {zip_path.name}"
                )
