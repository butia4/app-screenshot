"""Pure size-cap selection: the only rule that may delete archives."""

from collections.abc import Collection, Sequence
from pathlib import Path


def select_for_deletion(
    archives: Sequence[tuple[Path, int]], cap: int, protected: Collection[Path] = ()
) -> list[Path]:
    """`archives` is ordered oldest first. Deletes oldest until total <= cap.

    The newest archive and every `protected` archive (created in the current pass) are
    never selected, even if that leaves the total over the cap.
    """
    total = sum(size for _, size in archives)
    doomed: list[Path] = []
    for path, size in archives[:-1]:
        if total <= cap:
            break
        if path in protected:
            continue
        doomed.append(path)
        total -= size
    return doomed
