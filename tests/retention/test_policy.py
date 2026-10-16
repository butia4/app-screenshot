from pathlib import Path

from app_screenshot.retention.policy import select_for_deletion

MB = 1024**2


def arch(*sizes):
    return [(Path(f"a{i}.zip"), s * MB) for i, s in enumerate(sizes)]


def test_oldest_first_until_under_cap():
    assert select_for_deletion(arch(60, 50, 40), 100 * MB) == [Path("a0.zip")]


def test_nothing_when_under_cap():
    assert select_for_deletion(arch(10, 10), 100 * MB) == []


def test_newest_always_kept_even_if_over_cap():
    assert select_for_deletion(arch(10, 500), 100 * MB) == [Path("a0.zip")]
    assert select_for_deletion(arch(500), 100 * MB) == []


def test_protected_archives_are_skipped_oldest_first():
    a = arch(60, 50, 40)
    assert select_for_deletion(a, 100 * MB, protected={a[0][0]}) == [Path("a1.zip")]
    assert select_for_deletion(a, 10 * MB, protected={a[0][0], a[1][0]}) == []
