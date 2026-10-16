"""Filesystem adapter for the Storage port."""

import os
import shutil
from pathlib import Path


class FsStorage:
    def write_atomic(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        try:
            with open(tmp, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

    def list_files(self, d: Path, pattern: str) -> list[Path]:
        if not d.is_dir():
            return []
        return sorted(p for p in d.glob(pattern) if p.is_file())

    def size(self, p: Path) -> int:
        return p.stat().st_size

    def replace(self, src: Path, dst: Path) -> None:
        os.replace(src, dst)

    def delete(self, p: Path) -> None:
        p.unlink(missing_ok=True)

    def free_bytes(self, p: Path) -> int:
        probe = p
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        return shutil.disk_usage(probe).free

    def remove_empty_dir(self, p: Path) -> None:
        try:
            p.rmdir()
        except OSError:
            pass
