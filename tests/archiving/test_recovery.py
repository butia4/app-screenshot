import shutil

from app_screenshot.archiving.recovery import Recovery
from app_screenshot.archiving.service import ArchiveService
from app_screenshot.archiving.zip_archiver import ZipArchiver
from app_screenshot.shared.fs_storage import FsStorage
from tests.archiving.conftest import make_frames
from tests.fakes.notifier import FakeNotifier


def build(tmp_path):
    n, store, arch = FakeNotifier(), FsStorage(), ZipArchiver()
    service = ArchiveService(store, arch, n)
    return Recovery(store, arch, service, n), service, n


def session(tmp_path):
    s = tmp_path / "2026-01-01" / "session-090000"
    (s / "frames").mkdir(parents=True)
    (s / "archives").mkdir()
    return s


def test_removes_tmp_and_archives_loose_frames(tmp_path):
    rec, _, _ = build(tmp_path)
    s = session(tmp_path)
    make_frames(s / "frames", 12)
    (s / "archives" / "0001_x.zip.tmp").write_bytes(b"junk")
    rec.run(tmp_path)
    assert not list((s / "archives").glob("*.tmp"))
    assert not list((s / "frames").glob("*.webp"))
    zips = list((s / "archives").glob("*.zip"))
    assert len(zips) == 1
    assert len(ZipArchiver().read_index(zips[0])) == 12


def test_crash_between_replace_and_delete(tmp_path):
    rec, service, _ = build(tmp_path)
    s = session(tmp_path)
    make_frames(s / "frames", 4)
    backup = tmp_path / "backup"
    shutil.copytree(s / "frames", backup)
    service.archive(s / "frames", s / "archives")
    for f in backup.iterdir():  # simulate originals surviving the crash
        shutil.copy(f, s / "frames" / f.name)
    rec.run(tmp_path)
    assert not list((s / "frames").glob("*.webp"))
    assert len(list((s / "archives").glob("*.zip"))) == 1  # no duplicate zip


def test_new_frames_beside_old_zip_are_archived_not_lost(tmp_path):
    rec, service, _ = build(tmp_path)
    s = session(tmp_path)
    make_frames(s / "frames", 2)
    service.archive(s / "frames", s / "archives")
    make_frames(s / "frames", 3, start=30)
    rec.run(tmp_path)
    zips = sorted((s / "archives").glob("*.zip"))
    assert len(zips) == 2
    assert len(ZipArchiver().read_index(zips[1])) == 3


def test_corrupt_zip_never_deletes_frames(tmp_path):
    rec, _, _ = build(tmp_path)
    s = session(tmp_path)
    frames = make_frames(s / "frames", 2)
    (s / "archives" / "0001_a.zip").write_bytes(b"corrupt")
    rec.run(tmp_path)
    assert not any(f.exists() for f in frames)  # archived into a new verified zip
    assert any(len(ZipArchiver().read_index(z)) == 2 for z in (s / "archives").glob("0002_*.zip"))
