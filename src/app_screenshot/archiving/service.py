"""Archive pipeline: build .tmp -> verify -> atomic replace -> delete originals."""

import re
from collections.abc import Callable
from pathlib import Path

from app_screenshot.archiving.ports import Archiver
from app_screenshot.shared.layout import FRAME_PATTERNS, archive_seq, frame_seq
from app_screenshot.shared.notifier import Notifier
from app_screenshot.shared.storage import Storage

_TIME = re.compile(r"^\d{8}T(\d{6})-")


def list_frames(storage: Storage, frames_dir: Path) -> list[Path]:
    found: list[Path] = []
    for pattern in FRAME_PATTERNS:
        found.extend(storage.list_files(frames_dir, pattern))
    return sorted(found, key=lambda p: (frame_seq(p.name) or -1, p.name))


class ArchiveService:
    def __init__(
        self,
        storage: Storage,
        archiver: Archiver,
        notifier: Notifier,
        after_archive: Callable[[Path], None] | None = None,
    ) -> None:
        self._storage = storage
        self._archiver = archiver
        self._notifier = notifier
        self._after_archive = after_archive

    def archive(self, frames_dir: Path, archives_dir: Path) -> Path | None:
        """Archive all loose frames. Returns the final zip, or None (empty window/failure)."""
        try:
            frames = list_frames(self._storage, frames_dir)
        except OSError as exc:
            self._notifier.notify("warn", f"could not list frames in {frames_dir}: {exc}")
            return None
        if not frames:
            return None
        tmp: Path | None = None
        try:
            final = archives_dir / self._zip_name(archives_dir, frames)
            tmp = final.with_name(final.name + ".tmp")
            expected = {f.name: self._storage.size(f) for f in frames}
            self._archiver.build(tmp, frames)
            if not self._archiver.verify(tmp, expected):
                raise ValueError("verification failed (corrupt zip or member mismatch)")
            self._storage.replace(tmp, final)
        except Exception as exc:
            self._notifier.notify(
                "error", f"archive failed ({exc}); {len(frames)} frames kept, will retry"
            )
            if tmp is not None:
                self._discard(tmp)
            return None
        for frame in frames:
            try:
                self._storage.delete(frame)
            except OSError as exc:
                self._notifier.notify(
                    "warn", f"could not delete archived frame {frame.name}: {exc}"
                )
        self._storage.remove_empty_dir(frames_dir)
        self._notifier.notify("info", f"archived {len(frames)} frames -> {final.name}")
        if self._after_archive:
            try:
                self._after_archive(final)
            except OSError as exc:
                self._notifier.notify("warn", f"post-archive step failed: {exc}")
        return final

    def _discard(self, tmp: Path) -> None:
        """Best-effort cleanup after a failed build; never replaces the original error."""
        try:
            self._storage.delete(tmp)
        except OSError as exc:
            self._notifier.notify("warn", f"could not remove {tmp.name} ({exc}); recovery will")

    def _zip_name(self, archives_dir: Path, frames: list[Path]) -> str:
        seqs = [
            seq
            for p in self._storage.list_files(archives_dir, "*.zip")
            if (seq := archive_seq(p.name)) is not None
        ]
        return (
            f"{max(seqs, default=0) + 1:04d}_{self._stamp(frames[0])}-{self._stamp(frames[-1])}.zip"
        )

    @staticmethod
    def _stamp(frame: Path) -> str:
        m = _TIME.match(frame.name)
        return m.group(1) if m else "000000"
