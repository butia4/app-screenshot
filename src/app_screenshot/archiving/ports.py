"""Archiving port."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol


class Archiver(Protocol):
    def build(self, dest: Path, members: Sequence[Path]) -> None:
        """Write an uncompressed archive of `members` (arcname = basename) to `dest`."""
        ...

    def verify(self, path: Path, expected: Mapping[str, int]) -> bool:
        """True only if the archive is intact and holds exactly `expected` name -> size."""
        ...

    def read_index(self, path: Path) -> dict[str, int]:
        """Member name -> size of an existing archive. Raises on a corrupt archive."""
        ...

    def matching(self, zip_path: Path, loose: Mapping[str, Path]) -> set[str]:
        """Names in `loose` whose size and CRC32 equal the same-named member of the archive.

        Returns an empty set when the archive is unreadable or corrupt.
        """
        ...
