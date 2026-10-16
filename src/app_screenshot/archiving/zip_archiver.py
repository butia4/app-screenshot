"""zipfile adapter: ZIP_STORED (frames are already compressed)."""

import os
import zipfile
import zlib
from collections.abc import Mapping, Sequence
from pathlib import Path

_CHUNK = 1024 * 1024


def _crc32(path: Path) -> int:
    crc = 0
    with open(path, "rb") as fh:
        while chunk := fh.read(_CHUNK):
            crc = zlib.crc32(chunk, crc)
    return crc


class ZipArchiver:
    def build(self, dest: Path, members: Sequence[Path]) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_STORED) as zf:
            for member in members:
                zf.write(member, arcname=member.name)
        # fsync needs a descriptor with write access (FlushFileBuffers on Windows).
        fd = os.open(dest, os.O_RDWR | getattr(os, "O_BINARY", 0))
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

    def matching(self, zip_path: Path, loose: Mapping[str, Path]) -> set[str]:
        matched: set[str] = set()
        try:
            with zipfile.ZipFile(zip_path) as zf:
                if zf.testzip() is not None:
                    return set()
                for info in zf.infolist():
                    frame = loose.get(info.filename)
                    if frame is None:
                        continue
                    try:
                        if frame.stat().st_size == info.file_size and _crc32(frame) == info.CRC:
                            matched.add(info.filename)
                    except OSError:
                        continue
        except (OSError, zipfile.BadZipFile):
            return set()
        return matched
