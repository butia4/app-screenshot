"""Single-threaded capture loop: monotonic ticks, wall-clock gap detection, periodic archive."""

from collections.abc import Callable
from datetime import datetime

from app_screenshot.archiving.service import ArchiveService
from app_screenshot.capture.ports import Capturer
from app_screenshot.encoding.blank import BlankFrameMonitor
from app_screenshot.encoding.ports import Encoder
from app_screenshot.shared.clock import Clock
from app_screenshot.shared.layout import SessionLayout
from app_screenshot.shared.notifier import Notifier
from app_screenshot.shared.storage import Storage

EXIT_OK = 0
EXIT_FAILURE = 1
WAIT_CHUNK_S = 0.5


class CaptureSession:
    def __init__(
        self,
        *,
        clock: Clock,
        capturer: Capturer,
        encoder: Encoder,
        storage: Storage,
        notifier: Notifier,
        guard,  # object with ok() -> bool (DiskGuard)
        blank: BlankFrameMonitor,
        archiver: ArchiveService,
        layout: SessionLayout,
        capture_interval: float,
        archive_interval: float,
        wait: Callable[[float], bool],  # sleeps up to N s; True when stop was requested
        failure_limit: int = 10,
    ) -> None:
        self._clock = clock
        self._capturer = capturer
        self._encoder = encoder
        self._storage = storage
        self._notifier = notifier
        self._guard = guard
        self._blank = blank
        self._archiver = archiver
        self._layout = layout
        self._interval = capture_interval
        self._archive_interval = archive_interval
        self._wait = wait
        self._failure_limit = failure_limit
        self._seq = 0
        self._failures = 0

    def run(self) -> int:
        clock = self._clock
        next_tick = clock.monotonic()
        next_archive = next_tick + self._archive_interval
        last_mono, last_wall = clock.monotonic(), clock.now()
        exit_code = EXIT_OK
        stopped = False
        while not stopped:
            now, wall = clock.monotonic(), clock.now()
            if now >= next_tick:
                if self._gap(now - last_mono, wall - last_wall):
                    next_archive = now
                last_mono, last_wall = now, wall
                if not self._guard.ok():
                    pass  # paused: no capture, keep ticking to re-evaluate
                elif not self._capture_once():
                    exit_code = EXIT_FAILURE
                    break
                next_tick += self._interval
                if next_tick <= now:  # missed ticks are dropped, never burst
                    next_tick = now + self._interval
            if now >= next_archive:
                self._archiver.archive(self._layout.frames_dir, self._layout.archives_dir)
                next_archive = now + self._archive_interval
            remaining = max(0.0, min(next_tick, next_archive) - clock.monotonic())
            stopped = self._wait(min(remaining, WAIT_CHUNK_S))
        self._archiver.archive(self._layout.frames_dir, self._layout.archives_dir)
        return exit_code

    def _gap(self, mono_delta: float, wall_delta) -> bool:
        wall_s = wall_delta.total_seconds()
        if wall_s - mono_delta > 2 * self._interval or wall_s > 3 * self._interval:
            self._notifier.notify(
                "warn", f"resumed after a gap of ~{int(wall_s)}s (suspend?); missed ticks skipped"
            )
            return True
        return False

    def _capture_once(self) -> bool:
        """Returns False when the consecutive failure limit is reached."""
        try:
            frame = self._capturer.grab()
        except Exception as exc:
            self._failures += 1
            self._notifier.notify(
                "error", f"capture failed ({self._failures}/{self._failure_limit}): {exc}"
            )
            if self._failures >= self._failure_limit:
                self._notifier.notify("error", "too many consecutive capture failures; exiting")
                return False
            return True
        self._failures = 0
        try:
            self._blank.observe(self._encoder.luma_stddev(frame))
            data = self._encoder.encode(frame)
            self._seq += 1
            when: datetime = self._clock.now()
            name = self._layout.frame_name(when, self._seq, self._encoder.ext)
            self._storage.write_atomic(self._layout.frames_dir / name, data)
        except Exception as exc:  # FE-6: report, never abort
            self._notifier.notify("error", f"could not save frame: {exc}")
        return True
