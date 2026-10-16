import threading
from datetime import datetime

import pytest

from app_screenshot.archiving.service import ArchiveService
from app_screenshot.archiving.zip_archiver import ZipArchiver
from app_screenshot.capture.session import CaptureSession
from app_screenshot.encoding.blank import BlankFrameMonitor
from app_screenshot.shared.fs_storage import FsStorage
from app_screenshot.shared.layout import SessionLayout
from tests.fakes.capturer import FakeCapturer
from tests.fakes.clock import FakeClock
from tests.fakes.encoder import FakeEncoder
from tests.fakes.notifier import FakeNotifier


class Guard:
    def __init__(self, ok=True):
        self.allowed = ok

    def ok(self):
        return self.allowed


def build(tmp_path, *, capturer=None, guard=None, encoder=None, interval=60, archive=1800, **kw):
    clock, notifier, storage = FakeClock(), FakeNotifier(), FsStorage()
    layout = SessionLayout(tmp_path, "pc", datetime(2026, 1, 1, 9, 0, 0))
    stop = threading.Event()
    state = {"limit": None}

    def wait(timeout):
        clock.advance(timeout)
        if state["limit"] is not None and clock.monotonic() >= state["limit"]:
            stop.set()
        return stop.is_set()

    session = CaptureSession(
        clock=clock,
        capturer=capturer or FakeCapturer(),
        encoder=encoder or FakeEncoder(),
        storage=storage,
        notifier=notifier,
        guard=guard or Guard(),
        blank=BlankFrameMonitor(notifier, clock),
        archiver=ArchiveService(storage, ZipArchiver(), notifier),
        layout=layout,
        capture_interval=interval,
        archive_interval=archive,
        wait=wait,
        **kw,
    )

    def run_for(seconds):
        state["limit"] = clock.monotonic() + seconds
        return session.run()

    return session, run_for, clock, notifier, layout


def frames(layout):
    return list(layout.frames_dir.glob("*.webp")) if layout.frames_dir.exists() else []


def zips(layout):
    return sorted(layout.archives_dir.glob("*.zip")) if layout.archives_dir.exists() else []


def test_one_frame_per_tick_and_identical_frames_all_persisted(tmp_path):
    cap = FakeCapturer()
    _, run_for, _, _, layout = build(
        tmp_path, capturer=cap, archive=10_000, encoder=FakeEncoder(0.0)
    )
    run_for(60 * 5 - 1)
    assert cap.calls == 5
    (z,) = zips(layout)  # stop finalizes the archive; every frame is inside
    assert len(ZipArchiver().read_index(z)) == 5


def test_stop_finalizes_archive_exit_zero(tmp_path):
    # 7 ticks (t=0..360), stop right after -> final archive holds all 7
    _, run_for, _, _, layout = build(tmp_path, archive=10_000)
    assert run_for(60 * 6 + 1) == 0
    assert not frames(layout)
    (z,) = zips(layout)
    assert len(ZipArchiver().read_index(z)) == 7


def test_periodic_archive_during_run(tmp_path):
    _, run_for, *_, layout = build(tmp_path, archive=180)
    run_for(60 * 10)
    assert len(zips(layout)) >= 3
    assert not frames(layout)


def test_gap_takes_single_capture_and_reanchors(tmp_path):
    cap = FakeCapturer()
    session, _, clock, notifier, layout = build(tmp_path, capturer=cap, archive=10_000)
    state = {"n": 0}

    def wait(timeout):
        clock.advance(timeout)
        state["n"] += 1
        if state["n"] == 1:  # suspend: wall clock leaps an hour, then a tick is due
            clock.jump_wall(3600)
            clock.advance(60)
        return cap.calls >= 2

    session._wait = wait
    session.run()
    assert cap.calls == 2  # one capture after the gap, no burst of catch-up captures
    assert any("gap" in m for m in notifier.messages("warn"))
    assert len(zips(layout)) == 1  # gap forces an archive


def test_no_gap_notice_on_normal_ticks(tmp_path):
    _, run_for, _, notifier, _ = build(tmp_path, archive=10_000)
    run_for(60 * 4)
    assert not any("gap" in m for m in notifier.messages())


def test_transient_failures_continue(tmp_path):
    cap = FakeCapturer(fail_first=3)
    _, run_for, _, notifier, layout = build(tmp_path, capturer=cap, archive=10_000)
    assert run_for(60 * 6 - 1) == 0
    assert len(notifier.messages("error")) == 3
    assert cap.calls == 6


def test_failure_streak_exits_nonzero_at_limit(tmp_path):
    cap = FakeCapturer(always_fail=True)
    _, run_for, *_ = build(tmp_path, capturer=cap, failure_limit=10, archive=10_000)
    assert run_for(60 * 100) == 1
    assert cap.calls == 10


def test_custom_failure_limit(tmp_path):
    cap = FakeCapturer(always_fail=True)
    _, run_for, *_ = build(tmp_path, capturer=cap, failure_limit=3, archive=10_000)
    assert run_for(60 * 100) == 1
    assert cap.calls == 3


def test_paused_guard_skips_capture_but_keeps_ticking(tmp_path):
    cap, guard = FakeCapturer(), Guard(ok=False)
    _, run_for, *_ = build(tmp_path, capturer=cap, guard=guard, archive=10_000)
    run_for(60 * 3)
    assert cap.calls == 0
    guard.allowed = True
    run_for(60 * 3)
    assert cap.calls > 0


def test_encode_failure_reported_not_fatal(tmp_path):
    class BadEncoder(FakeEncoder):
        def encode(self, frame):
            raise RuntimeError("boom")

    cap = FakeCapturer()
    _, run_for, _, notifier, _ = build(tmp_path, capturer=cap, encoder=BadEncoder(), archive=10_000)
    assert run_for(60 * 3 - 1) == 0
    assert cap.calls == 3 and len(notifier.messages("error")) == 3


def test_archive_exception_mid_loop_still_runs_final_archive(tmp_path):
    session, _, _, notifier, _ = build(tmp_path, archive=120)
    calls = []

    def archive(frames_dir, archives_dir):
        calls.append(1)
        raise RuntimeError("archive blew up")

    session._archiver.archive = archive
    with pytest.raises(RuntimeError, match="archive blew up"):
        session.run()
    assert len(calls) == 2  # the periodic one that crashed the loop, then the final attempt
    assert any("final archive failed" in m for m in notifier.messages("error"))


def test_final_archive_failure_does_not_change_exit_code(tmp_path):
    session, run_for, _, notifier, _ = build(tmp_path, archive=10_000)

    def archive(frames_dir, archives_dir):
        raise OSError("disk gone")

    session._archiver.archive = archive
    assert run_for(60 * 2) == 0
    assert any("final archive failed" in m for m in notifier.messages("error"))


def test_slow_archive_work_is_not_a_gap(tmp_path):
    session, run_for, clock, notifier, _ = build(tmp_path, interval=1, archive=2)
    real = session._archiver.archive

    def slow_archive(*a, **k):
        clock.advance(5)  # slow work moves wall and monotonic time together
        return real(*a, **k)

    session._archiver.archive = slow_archive
    run_for(10)
    assert not any("gap" in m for m in notifier.messages())


def test_suspend_with_stalled_monotonic_is_a_gap(tmp_path):
    cap = FakeCapturer()
    session, _, clock, notifier, _ = build(tmp_path, capturer=cap, archive=10_000)
    state = {"n": 0}

    def wait(timeout):
        state["n"] += 1
        if state["n"] == 1:  # monotonic paused (Linux/macOS), wall leaps
            clock.jump_wall(3600)
        else:
            clock.advance(timeout)
        return cap.calls >= 2

    session._wait = wait
    session.run()
    assert any("gap" in m for m in notifier.messages("warn"))


def test_suspend_with_running_monotonic_is_a_gap_via_oversleep(tmp_path):
    cap = FakeCapturer()
    session, _, clock, notifier, _ = build(tmp_path, capturer=cap, interval=1, archive=10_000)
    state = {"n": 0}

    def wait(timeout):
        state["n"] += 1
        # Windows-style: monotonic includes the suspend; wall and mono advance equally, so the
        # wall-vs-mono rule alone cannot see it, but the wait took 3600 s instead of `timeout`.
        clock.advance(3600 if state["n"] == 1 else timeout)
        return cap.calls >= 2

    session._wait = wait
    session.run()
    assert any("gap" in m for m in notifier.messages("warn"))


def test_backward_wall_step_is_not_a_gap(tmp_path):
    session, _, clock, notifier, _ = build(tmp_path, archive=10_000)
    state = {"n": 0}

    def wait(timeout):
        state["n"] += 1
        clock.advance(timeout)
        if state["n"] == 1:
            clock.jump_wall(-3600)
        return state["n"] >= 5

    session._wait = wait
    session.run()
    assert not any("gap" in m for m in notifier.messages())


def test_save_failures_exit_nonzero_after_final_archive(tmp_path):
    class BadEncoder(FakeEncoder):
        def encode(self, frame):
            raise RuntimeError("boom")

    session, run_for, *_ = build(tmp_path, encoder=BadEncoder(), failure_limit=3, archive=10_000)
    archived = []
    real = session._archiver.archive
    session._archiver.archive = lambda *a, **k: (archived.append(1), real(*a, **k))[1]
    assert run_for(60 * 100) == 1
    assert archived  # the final archive ran before exiting


def test_save_failure_counter_resets_on_success(tmp_path):
    class FlakyEncoder(FakeEncoder):
        def encode(self, frame):
            if self.encoded in (0, 1, 3, 4):  # fail, fail, ok, fail, fail, ok ...
                self.encoded += 1
                raise RuntimeError("boom")
            return super().encode(frame)

    cap = FakeCapturer()
    _, run_for, *_ = build(
        tmp_path, capturer=cap, encoder=FlakyEncoder(), failure_limit=3, archive=10_000
    )
    assert run_for(60 * 6 - 1) == 0
    assert cap.calls == 6


def test_grab_and_save_failure_counters_are_independent(tmp_path):
    class Alternating(FakeCapturer):
        def grab(self):
            n = self.calls + 1  # FakeCapturer.grab counts the call itself
            if n in (1, 3):
                self.calls = n
                raise RuntimeError("grab failed")
            return super().grab()

    class SaveFailsOnEven(FakeEncoder):
        def encode(self, frame):
            self.encoded += 1
            if self.encoded in (1, 2):
                raise RuntimeError("boom")
            return b"ok"

    cap = Alternating()
    # ticks: 1 grab-fail, 2 save-fail, 3 grab-fail, 4 save-fail, 5 ok
    # (encode runs only after a successful grab: calls 2 and 4 are the save failures)
    _, run_for, *_ = build(
        tmp_path, capturer=cap, encoder=SaveFailsOnEven(), failure_limit=3, archive=10_000
    )
    assert run_for(60 * 5 - 1) == 0
    assert cap.calls == 5
