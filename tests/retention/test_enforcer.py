from app_screenshot.retention.enforcer import RetentionEnforcer
from app_screenshot.shared.fs_storage import FsStorage
from tests.fakes.notifier import FakeNotifier
from tests.fakes.storage import FailingStorage

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


def test_failed_delete_warns_and_next_candidates_are_processed(tmp_path):
    a = make_archive(tmp_path, "2026-01-01", "session-090000", "0001.zip", 40)
    b = make_archive(tmp_path, "2026-01-02", "session-090000", "0001.zip", 40)
    c = make_archive(tmp_path, "2026-01-03", "session-090000", "0001.zip", 40)
    store, n = FailingStorage(), FakeNotifier()
    store.fail("delete", lambda p: p == a)
    RetentionEnforcer(store, n, tmp_path, 50).enforce()
    assert a.exists() and not b.exists() and c.exists()
    assert any(a.name in m for m in n.messages("warn"))


def test_size_and_list_errors_are_skipped(tmp_path):
    a = make_archive(tmp_path, "2026-01-01", "session-090000", "0001.zip", 60)
    b = make_archive(tmp_path, "2026-01-02", "session-090000", "0001.zip", 60)
    store, n = FailingStorage(), FakeNotifier()
    store.fail("size", lambda p: p == a)
    RetentionEnforcer(store, n, tmp_path, 100).enforce()
    assert a.exists() and b.exists() and n.messages("warn")
    store2, n2 = FailingStorage(), FakeNotifier()
    store2.fail("list_files")
    RetentionEnforcer(store2, n2, tmp_path, 1).enforce()  # must not raise
    assert n2.messages("warn")


def test_numeric_sequence_order_9999_before_10000(tmp_path):
    old = make_archive(tmp_path, "2026-01-01", "session-090000", "9999_a.zip", 60)
    new = old.parent / "10000_a.zip"
    new.write_bytes(b"x" * 60)
    RetentionEnforcer(FsStorage(), FakeNotifier(), tmp_path, 100).enforce()
    assert not old.exists() and new.exists()


def test_over_cap_warning_fires_once_per_episode_and_rearms(tmp_path):
    a = make_archive(tmp_path, "2026-01-01", "session-090000", "0001.zip", 200)
    n = FakeNotifier()
    enforcer = RetentionEnforcer(FsStorage(), n, tmp_path, 100)
    for _ in range(3):
        enforcer.enforce()
    assert len(n.messages("warn")) == 1
    a.write_bytes(b"x" * 50)  # total back under the cap: episode over
    enforcer.enforce()
    a.write_bytes(b"x" * 200)
    enforcer.enforce()
    assert len(n.messages("warn")) == 2


def test_over_cap_warning_names_failed_deletions(tmp_path):
    a = make_archive(tmp_path, "2026-01-01", "session-090000", "0001.zip", 60)
    make_archive(tmp_path, "2026-01-02", "session-090000", "0001.zip", 60)
    store, n = FailingStorage(), FakeNotifier()
    store.fail("delete", lambda p: p == a)
    enforcer = RetentionEnforcer(store, n, tmp_path, 100)
    enforcer.enforce()
    enforcer.enforce()  # still once per episode
    over = [m for m in n.messages("warn") if "exceeds cap" in m]
    assert len(over) == 1 and "1 archive(s) could not be deleted" in over[0]
    assert not any("newest or just-created" in m for m in n.messages("warn"))


def test_over_cap_warning_names_protected_archives_without_failures(tmp_path):
    make_archive(tmp_path, "2026-01-01", "session-090000", "0001.zip", 200)
    n = FakeNotifier()
    RetentionEnforcer(FsStorage(), n, tmp_path, 100).enforce()
    warns = n.messages("warn")
    assert len(warns) == 1 and "newest or just-created" in warns[0]
    assert "could not be deleted" not in warns[0]
