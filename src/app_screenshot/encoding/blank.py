"""Blank-frame monitor. Warning only: it never discards or alters a frame."""

from app_screenshot.shared.clock import Clock
from app_screenshot.shared.notifier import Notifier

UNIFORM_STDDEV = 2.0


class BlankFrameMonitor:
    def __init__(
        self,
        notifier: Notifier,
        clock: Clock,
        *,
        consecutive: int = 3,
        min_gap_s: float = 600.0,
        threshold: float = UNIFORM_STDDEV,
    ) -> None:
        self._notifier = notifier
        self._clock = clock
        self._consecutive = consecutive
        self._min_gap_s = min_gap_s
        self._threshold = threshold
        self._streak = 0
        self._last_warn: float | None = None

    def observe(self, stddev: float) -> None:
        if stddev >= self._threshold:
            self._streak = 0
            return
        self._streak += 1
        if self._streak < self._consecutive:
            return
        now = self._clock.monotonic()
        if self._last_warn is not None and now - self._last_warn < self._min_gap_s:
            return
        self._last_warn = now
        self._notifier.notify(
            "warn",
            f"{self._streak} consecutive blank/uniform frames: capture may be blocked "
            "(e.g. macOS Screen Recording permission). Frames are still being saved.",
        )
