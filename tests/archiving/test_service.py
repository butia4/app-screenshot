from app_screenshot.archiving.service import ArchiveService
from app_screenshot.archiving.zip_archiver import ZipArchiver
from app_screenshot.shared.fs_storage import FsStorage
from tests.archiving.conftest import make_frames
from tests.fakes.notifier import FakeNotifier
from tests.fakes.storage import FailingStorage


def test_archives_verifies_and_deletes_originals(env):
    frames, archives, service, notifier, calls = env
    make_frames(frames, 5)
    final = service.archive(frames, archives)
    assert final is not None and final.exists()
    assert final.name.startswith("0001_090000-")
    assert not list(frames.glob("*.webp"))
    assert not list(archives.glob("*.tmp"))
    assert calls == [final]  # retention hook receives the new archive


def test_empty_window_creates_no_zip(env):
    frames, archives, service, _, calls = env
    assert service.archive(frames, archives) is None
    assert not archives.exists() and calls == []


def test_sequence_increments(env):
    frames, archives, service, *_ = env
    make_frames(frames, 2)
    first = service.archive(frames, archives)
    make_frames(frames, 2, start=10)
    second = service.archive(frames, archives)
    assert first.name[:4] == "0001" and second.name[:4] == "0002"


def test_verify_failure_keeps_frames_and_retries(env, monkeypatch):
    frames, archives, service, notifier, calls = env
    paths = make_frames(frames, 4)
    real = service._archiver.verify
    monkeypatch.setattr(service._archiver, "verify", lambda *a, **k: False)
    assert service.archive(frames, archives) is None
    assert all(p.exists() for p in paths)
    assert not list(archives.glob("*.tmp")) and not list(archives.glob("*.zip"))
    assert notifier.messages("error") and calls == []
    monkeypatch.setattr(service._archiver, "verify", real)
    make_frames(frames, 1, start=20)
    final = service.archive(frames, archives)
    assert final is not None and not list(frames.glob("*.webp"))
    assert len(service._archiver.read_index(final)) == 5


def test_build_error_keeps_frames(env, monkeypatch):
    frames, archives, service, notifier, _ = env
    paths = make_frames(frames, 3)

    def boom(dest, members):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr(service._archiver, "build", boom)
    assert service.archive(frames, archives) is None
    assert all(p.exists() for p in paths)
    assert not list(archives.glob("*.tmp"))


def test_tmp_delete_failure_never_masks_the_original_error(tmp_path):
    frames, archives = tmp_path / "frames", tmp_path / "archives"
    store, notifier = FailingStorage(), FakeNotifier()
    store.fail("delete", lambda p: p.name.endswith(".tmp"))
    service = ArchiveService(store, ZipArchiver(), notifier)
    service._archiver.verify = lambda *a, **k: False
    paths = make_frames(frames, 2)
    assert service.archive(frames, archives) is None
    assert all(p.exists() for p in paths)
    errors, warns = notifier.messages("error"), notifier.messages("warn")
    assert errors and "verification failed" in errors[0]
    assert warns and ".tmp" in warns[0]


def test_size_error_follows_the_keep_and_retry_path(tmp_path):
    frames, archives = tmp_path / "frames", tmp_path / "archives"
    store, notifier = FailingStorage(), FakeNotifier()
    store.fail("size", lambda p: p.suffix == ".webp")
    service = ArchiveService(store, ZipArchiver(), notifier)
    paths = make_frames(frames, 2)
    assert service.archive(frames, archives) is None
    assert all(p.exists() for p in paths) and notifier.messages("error")


def test_list_frames_oserror_warns_and_returns_none(tmp_path):
    store, notifier = FailingStorage(), FakeNotifier()
    store.fail("list_files")
    service = ArchiveService(store, ZipArchiver(), notifier)
    assert service.archive(tmp_path / "frames", tmp_path / "archives") is None
    assert notifier.messages("warn")


def test_after_archive_oserror_warns_and_still_returns_final(tmp_path):
    frames, archives = tmp_path / "frames", tmp_path / "archives"
    notifier = FakeNotifier()

    def hook(_):
        raise PermissionError("locked")

    service = ArchiveService(FsStorage(), ZipArchiver(), notifier, after_archive=hook)
    make_frames(frames, 2)
    final = service.archive(frames, archives)
    assert final is not None and final.exists()
    assert any("locked" in m for m in notifier.messages("warn"))


def test_sequence_continues_past_9999(env):
    frames, archives, service, *_ = env
    archives.mkdir()
    (archives / "9999_090000-090000.zip").write_bytes(b"x")
    (archives / "10000_090000-090000.zip").write_bytes(b"x")
    make_frames(frames, 1)
    final = service.archive(frames, archives)
    assert final.name.startswith("10001_")


def test_frames_dir_removed_after_successful_archive(env):
    frames, archives, service, *_ = env
    make_frames(frames, 2)
    assert service.archive(frames, archives) is not None
    assert not frames.exists()


def test_backward_timestamps_zip_in_sequence_order(env):
    frames, archives, service, *_ = env
    # wall clock stepped back 1 h between frames 2 and 3: text order differs from sequence
    for name in (
        "20260101T100000-00001.webp",
        "20260101T100100-00002.webp",
        "20260101T090000-00003.webp",
    ):
        (frames / name).write_bytes(b"x" + name.encode())
    final = service.archive(frames, archives)
    assert final.name == "0001_100000-090000.zip"
    assert list(ZipArchiver().read_index(final)) == [
        "20260101T100000-00001.webp",
        "20260101T100100-00002.webp",
        "20260101T090000-00003.webp",
    ]
