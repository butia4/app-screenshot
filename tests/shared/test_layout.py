from datetime import datetime
from pathlib import Path

from app_screenshot.shared.fs_storage import FsStorage
from app_screenshot.shared.layout import SessionLayout, sanitize_hostname

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
