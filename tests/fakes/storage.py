from collections.abc import Callable
from pathlib import Path

from app_screenshot.shared.fs_storage import FsStorage


class FailingStorage(FsStorage):
    """FsStorage that raises PermissionError for configured (method, predicate) pairs."""

    def __init__(self) -> None:
        self._rules: list[tuple[str, Callable[[Path], bool]]] = []

    def fail(self, method: str, predicate: Callable[[Path], bool] = lambda p: True) -> None:
        self._rules.append((method, predicate))

    def _check(self, method: str, p: Path) -> None:
        if any(m == method and pred(p) for m, pred in self._rules):
            raise PermissionError(f"{method} denied: {p}")

    def list_files(self, d: Path, pattern: str) -> list[Path]:
        self._check("list_files", d)
        return super().list_files(d, pattern)

    def size(self, p: Path) -> int:
        self._check("size", p)
        return super().size(p)

    def delete(self, p: Path) -> None:
        self._check("delete", p)
        super().delete(p)
