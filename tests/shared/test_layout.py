from datetime import datetime
from pathlib import Path

from app_screenshot.shared.fs_storage import FsStorage
from app_screenshot.shared.layout import (
    SessionLayout,
    archive_seq,
    archive_sort_key,
    frame_seq,
    sanitize_hostname,
    session_key,
)

WHEN = datetime(2026, 3, 4, 9, 5, 7)


def test_paths():
    lay = SessionLayout(Path("/out"), "pc", WHEN)
    assert lay.session_dir == Path("/out/pc/2026-03-04/session-090507")
    assert lay.frames_dir == lay.session_dir / "frames"
    assert lay.archives_dir == lay.session_dir / "archives"
    assert lay.frame_name(WHEN, 3, "webp") == "20260304T090507-00003.webp"


def test_hostname_sanitized():
    assert sanitize_hostname("my pc/../x") == "my_pc_.._x"
    assert sanitize_hostname("///") == "host"


def test_dirs_are_lazy_and_write_atomic_creates_them(tmp_path):
    lay = SessionLayout(tmp_path, "pc", WHEN)
    assert not lay.session_dir.exists()
    target = lay.frames_dir / "a.webp"
    FsStorage().write_atomic(target, b"data")
    assert target.read_bytes() == b"data"
    assert not list(lay.frames_dir.glob("*.tmp"))


def test_archive_and_frame_seq_accept_any_width():
    assert archive_seq("0001_a.zip") == 1
    assert archive_seq("9999_a.zip") == 9999
    assert archive_seq("10000_a.zip") == 10000
    assert archive_seq("notes.zip") is None
    assert frame_seq("20260101T090000-00005.webp") == 5
    assert frame_seq("20260101T090000-123456.jpg") == 123456
    assert frame_seq("junk.webp") is None


def test_session_key_orders_suffixes_numerically():
    names = ["session-101500-10", "session-101500-2", "session-101500", "session-090000"]
    assert sorted(names, key=session_key) == [
        "session-090000",
        "session-101500",
        "session-101500-2",
        "session-101500-10",
    ]


def test_archive_sort_key_is_numeric_by_sequence(tmp_path):
    d = tmp_path / "2026-01-01" / "session-090000" / "archives"
    a, b = d / "9999_x.zip", d / "10000_x.zip"
    assert sorted([b, a], key=archive_sort_key) == [a, b]


def test_allocate_suffixes_on_collision(tmp_path):
    first = SessionLayout.allocate(tmp_path, "pc", WHEN, lambda p: p.exists())
    assert first.session_dir.name == "session-090507"
    first.frames_dir.mkdir(parents=True)
    second = SessionLayout.allocate(tmp_path, "pc", WHEN, lambda p: p.exists())
    assert second.session_dir.name == "session-090507-2"
    second.frames_dir.mkdir(parents=True)
    third = SessionLayout.allocate(tmp_path, "pc", WHEN, lambda p: p.exists())
    assert third.session_dir.name == "session-090507-3"
    assert third.frames_dir == third.session_dir / "frames"
