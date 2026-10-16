import pytest

from app_screenshot.archiving.service import ArchiveService
from app_screenshot.archiving.zip_archiver import ZipArchiver
from app_screenshot.shared.fs_storage import FsStorage
from tests.fakes.notifier import FakeNotifier


@pytest.fixture
def env(tmp_path):
    frames, archives = tmp_path / "frames", tmp_path / "archives"
    frames.mkdir()
    notifier = FakeNotifier()
    calls = []
    service = ArchiveService(FsStorage(), ZipArchiver(), notifier, after_archive=calls.append)
    return frames, archives, service, notifier, calls


def make_frames(frames_dir, n, start=0):
    frames_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(start, start + n):
        p = frames_dir / f"20260101T09{i:02d}00-{i:05d}.webp"
        p.write_bytes(b"data-%d" % i)
        paths.append(p)
    return paths
