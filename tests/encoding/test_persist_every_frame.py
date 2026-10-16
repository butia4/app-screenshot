"""FE-5 / FE-6 at encode+store level: nothing is discarded, failures do not abort."""

from pathlib import Path

from app_screenshot.encoding.ports import RawFrame
from app_screenshot.shared.fs_storage import FsStorage
from tests.fakes.encoder import FakeEncoder


def test_identical_frames_both_persisted(tmp_path):
    enc, store = FakeEncoder(stddev=0.0), FsStorage()
    same = RawFrame(4, 4, b"\x00" * 48)
    for i in range(2):
        store.write_atomic(tmp_path / f"f{i}.webp", enc.encode(same))
    assert len(store.list_files(tmp_path, "*.webp")) == 2


def test_write_failure_is_an_exception_the_caller_can_report(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_bytes(b"x")
    store = FsStorage()
    try:
        store.write_atomic(Path(blocker) / "sub" / "f.webp", b"d")
    except OSError:
        pass
    else:
        raise AssertionError("expected OSError")
    assert not list(tmp_path.glob("**/*.tmp"))
