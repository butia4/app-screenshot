"""zipfile adapter: ZIP_STORED (frames are already compressed)."""

import os
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path


class ZipArchiver:
    def build(self, dest: Path, members: Sequence[Path]) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_STORED) as zf:
            for member in members:
                zf.write(member, arcname=member.name)
        fd = os.open(dest, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def verify(self, path: Path, expected: Mapping[str, int]) -> bool:
        try:
            with zipfile.ZipFile(path) as zf:
                if zf.testzip() is not None:
                    return False
                actual = {i.filename: i.file_size for i in zf.infolist()}
        except (OSError, zipfile.BadZipFile):
            return False
        return actual == dict(expected)

    def read_index(self, path: Path) -> dict[str, int]:
        with zipfile.ZipFile(path) as zf:
            return {i.filename: i.file_size for i in zf.infolist()}
