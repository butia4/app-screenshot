from app_screenshot.retention.enforcer import RetentionEnforcer
from app_screenshot.shared.fs_storage import FsStorage
from tests.fakes.notifier import FakeNotifier

MB = 1024**2


def make_archive(host, date, session, name, size):
    d = host / date / session / "archives"
    d.mkdir(parents=True)
    p = d / name
    p.write_bytes(b"x" * size)
    return p


def test_deletes_oldest_and_prunes_empty_dirs(tmp_path):
    a = make_archive(tmp_path, "2026-01-01", "session-090000", "0001.zip", 60)
    b = make_archive(tmp_path, "2026-01-02", "session-090000", "0001.zip", 50)
    c = make_archive(tmp_path, "2026-01-02", "session-100000", "0001.zip", 40)
    RetentionEnforcer(FsStorage(), FakeNotifier(), tmp_path, 100).enforce()
    assert not a.exists() and b.exists() and c.exists()
    assert not (tmp_path / "2026-01-01").exists()


def test_never_touches_frames_or_foreign_files(tmp_path):
    a = make_archive(tmp_path, "2026-01-01", "session-090000", "0001.zip", 60)
    b = make_archive(tmp_path, "2026-01-01", "session-100000", "0001.zip", 60)
    frames = a.parent.parent / "frames"
    frames.mkdir()
    (frames / "f.webp").write_bytes(b"f")
    foreign = tmp_path / "2026-01-01" / "notes.zip"
    foreign.write_bytes(b"z" * 500)
    RetentionEnforcer(FsStorage(), FakeNotifier(), tmp_path, 100).enforce()
    assert not a.exists() and b.exists()
    assert (frames / "f.webp").exists() and foreign.exists()


def test_single_oversized_archive_kept_with_warning(tmp_path):
    a = make_archive(tmp_path, "2026-01-01", "session-090000", "0001.zip", 200)
    n = FakeNotifier()
    RetentionEnforcer(FsStorage(), n, tmp_path, 100).enforce()
    assert a.exists() and n.messages("warn")


def test_enforce_protects_just_created_even_if_oldest(tmp_path):
    old = make_archive(tmp_path, "2026-01-01", "session-090000", "0001.zip", 80)
    other = make_archive(tmp_path, "2026-01-02", "session-090000", "0001.zip", 80)
    n = FakeNotifier()
    RetentionEnforcer(FsStorage(), n, tmp_path, 100).enforce([old])
    assert old.exists() and other.exists()  # newest kept, protected kept; cap exceeded
    assert n.messages("warn")


def test_no_warning_when_under_cap_after_deletion(tmp_path):
    make_archive(tmp_path, "2026-01-01", "session-090000", "0001.zip", 60)
    make_archive(tmp_path, "2026-01-02", "session-090000", "0001.zip", 60)
    n = FakeNotifier()
    RetentionEnforcer(FsStorage(), n, tmp_path, 100).enforce()
    assert not n.messages("warn")


def test_on_archive_protects_created_and_deletes_older(tmp_path):
    a = make_archive(tmp_path, "2026-01-01", "session-090000", "0001.zip", 60)
    b = make_archive(tmp_path, "2026-01-02", "session-090000", "0001.zip", 60)
    c = make_archive(tmp_path, "2026-01-03", "session-090000", "0001.zip", 60)
    RetentionEnforcer(FsStorage(), FakeNotifier(), tmp_path, 100).on_archive(b)
    assert not a.exists() and b.exists() and c.exists()
