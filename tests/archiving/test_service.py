from tests.archiving.conftest import make_frames


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
