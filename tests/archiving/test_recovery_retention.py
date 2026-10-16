"""Startup ordering: recovery archives are never deleted by the retention of that same pass."""

from app_screenshot.archiving.recovery import Recovery
from app_screenshot.archiving.service import ArchiveService
from app_screenshot.archiving.zip_archiver import ZipArchiver
from app_screenshot.retention.enforcer import RetentionEnforcer
from app_screenshot.shared.fs_storage import FsStorage
from tests.archiving.conftest import make_frames
from tests.fakes.notifier import FakeNotifier


def wire(host, cap):
    n, store, arch = FakeNotifier(), FsStorage(), ZipArchiver()
    enforcer = RetentionEnforcer(store, n, host, cap)
    service = ArchiveService(store, arch, n, after_archive=enforcer.on_archive)
    return Recovery(store, arch, service, n), enforcer


def old_session(host, date, name, count):
    s = host / date / name
    (s / "frames").mkdir(parents=True)
    make_frames(s / "frames", count)
    return s


def run_startup(rec, enforcer, host):
    enforcer.begin_startup()
    try:
        rec.run(host)
    finally:
        enforcer.end_startup()


def test_recovery_archives_survive_cap_in_same_pass(tmp_path):
    s1 = old_session(tmp_path, "2026-01-01", "session-090000", 3)
    s2 = old_session(tmp_path, "2026-01-02", "session-090000", 3)
    rec, enforcer = wire(tmp_path, cap=1)  # far below any archive size
    run_startup(rec, enforcer, tmp_path)
    assert len(list((s1 / "archives").glob("*.zip"))) == 1
    assert len(list((s2 / "archives").glob("*.zip"))) == 1


def test_next_pass_enforces_cap_oldest_first(tmp_path):
    s1 = old_session(tmp_path, "2026-01-01", "session-090000", 3)
    s2 = old_session(tmp_path, "2026-01-02", "session-090000", 3)
    rec, enforcer = wire(tmp_path, cap=1)
    run_startup(rec, enforcer, tmp_path)
    newest = s2 / "archives"
    make_frames(s2 / "frames", 2, start=20)
    service = ArchiveService(FsStorage(), ZipArchiver(), FakeNotifier(), enforcer.on_archive)
    created = service.archive(s2 / "frames", newest)
    assert created is not None and created.exists()
    assert not list((s1 / "archives").glob("*.zip"))  # older one now removed by size cap
