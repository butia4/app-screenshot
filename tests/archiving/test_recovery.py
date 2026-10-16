import shutil
import zipfile

from app_screenshot.archiving.recovery import Recovery
from app_screenshot.archiving.service import ArchiveService
from app_screenshot.archiving.zip_archiver import ZipArchiver
from app_screenshot.shared.fs_storage import FsStorage
from tests.archiving.conftest import make_frames
from tests.fakes.notifier import FakeNotifier
from tests.fakes.storage import FailingStorage


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
    (s / "frames").mkdir(exist_ok=True)  # the archive step prunes the emptied dir
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


def test_same_name_and_size_but_different_bytes_is_kept_and_archived(tmp_path):
    rec, service, notifier = build(tmp_path)
    s = session(tmp_path)
    (frame,) = make_frames(s / "frames", 1)
    service.archive(s / "frames", s / "archives")
    frame.parent.mkdir(exist_ok=True)
    frame.write_bytes(b"DATA-0")  # the zip holds b"data-0": same name and size, other content
    rec.run(tmp_path)
    assert any("differs" in m for m in notifier.messages("warn"))
    assert not frame.exists()  # archived into a new zip, not silently dropped
    zips = sorted((s / "archives").glob("*.zip"))
    assert len(zips) == 2
    with zipfile.ZipFile(zips[1]) as zf:
        assert zf.read(frame.name) == b"DATA-0"


def test_identical_frames_are_deleted_without_a_new_zip(tmp_path):
    rec, service, _ = build(tmp_path)
    s = session(tmp_path)
    (frame,) = make_frames(s / "frames", 1)
    service.archive(s / "frames", s / "archives")
    frame.parent.mkdir(exist_ok=True)
    frame.write_bytes(b"data-0")
    rec.run(tmp_path)
    assert not frame.exists()
    assert len(list((s / "archives").glob("*.zip"))) == 1


def test_undeletable_tmp_warns_and_startup_completes(tmp_path):
    n, store, arch = FakeNotifier(), FailingStorage(), ZipArchiver()
    store.fail("delete", lambda p: p.name.endswith(".tmp"))
    rec = Recovery(store, arch, ArchiveService(store, arch, n), n)
    s = session(tmp_path)
    make_frames(s / "frames", 2)
    (s / "archives" / "0001_x.zip.tmp").write_bytes(b"junk")
    rec.run(tmp_path)
    assert any("could not remove leftover" in m for m in n.messages("warn"))
    assert len(list((s / "archives").glob("*.zip"))) == 1  # frames still archived


def test_undeletable_covered_frame_warns_and_continues(tmp_path):
    n, store, arch = FakeNotifier(), FailingStorage(), ZipArchiver()
    rec = Recovery(store, arch, ArchiveService(store, arch, n), n)
    s = session(tmp_path)
    paths = make_frames(s / "frames", 2)
    ArchiveService(FsStorage(), arch, FakeNotifier()).archive(s / "frames", s / "archives")
    (s / "frames").mkdir(exist_ok=True)
    for p in paths:
        p.write_bytes(b"data-%d" % int(p.name.split("-")[1].split(".")[0]))
    store.fail("delete", lambda p: p == paths[0])
    rec.run(tmp_path)
    assert any("could not delete" in m for m in n.messages("warn"))
    assert paths[0].exists() and not paths[1].exists()
