"""Startup ordering: recovery archives are never deleted by the retention of that same pass."""

import zipfile

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


def all_captures(host):
    """Every capture under `host`, loose or archived, keyed by (session, frame name)."""
    found = {(p.parent.parent.name, p.name) for p in host.rglob("frames/*.webp")}
    for z in host.rglob("archives/*.zip"):
        found |= {(z.parent.parent.name, m) for m in zipfile.ZipFile(z).namelist()}
    return found


def test_restarts_under_cap_never_lose_a_capture(tmp_path):
    store, arch = FsStorage(), ZipArchiver()
    plain = ArchiveService(store, arch, FakeNotifier())
    # interrupted mid-run: two archived windows plus loose frames not yet archived
    a = old_session(tmp_path, "2026-01-01", "session-090000", 3)
    plain.archive(a / "frames", a / "archives")
    make_frames(a / "frames", 3, start=10)
    plain.archive(a / "frames", a / "archives")
    make_frames(a / "frames", 4, start=20)
    # crash between zip replace and frame delete, plus a half-written frame
    b = old_session(tmp_path, "2026-01-02", "session-090000", 3)
    (b / "archives").mkdir()
    arch.build(b / "archives" / "0001_090000-090200.zip", sorted((b / "frames").glob("*.webp")))
    (b / "frames" / "partial.webp.tmp").write_bytes(b"x")
    before = all_captures(tmp_path)

    for _ in range(3):
        run_startup(*wire(tmp_path, cap=2**30), tmp_path)

    assert all_captures(tmp_path) == before
    assert not list(tmp_path.rglob("frames/*.webp"))  # everything ended up archived


def test_archive_numbers_cross_9999_and_retention_deletes_numerically(tmp_path):
    store, arch, n = FsStorage(), ZipArchiver(), FakeNotifier()
    s = tmp_path / "2026-01-01" / "session-090000"
    archives = s / "archives"
    archives.mkdir(parents=True)
    (archives / "9999_090000-090000.zip").write_bytes(b"x" * 1000)
    enforcer = RetentionEnforcer(store, n, tmp_path, 1100)
    service = ArchiveService(store, arch, n, after_archive=enforcer.on_archive)
    make_frames(s / "frames", 1)
    first = service.archive(s / "frames", archives)
    make_frames(s / "frames", 1, start=10)
    second = service.archive(s / "frames", archives)
    assert first.name.startswith("10000_") and second.name.startswith("10001_")
    # 9999_ (oldest by number, though "9999" > "10000" as text) is the one that went
    assert not (archives / "9999_090000-090000.zip").exists()
    assert first.exists() and second.exists()
