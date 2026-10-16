from datetime import UTC, datetime, timedelta


class FakeClock:
    """Manually advanced clock; wall time can jump independently (suspend)."""

    def __init__(self, start: datetime | None = None) -> None:
        self._mono = 1000.0
        self._wall = start or datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)

    def monotonic(self) -> float:
        return self._mono

    def now(self) -> datetime:
        return self._wall

    def advance(self, seconds: float) -> None:
        self._mono += seconds
        self._wall += timedelta(seconds=seconds)

    def jump_wall(self, seconds: float) -> None:
        """Advance wall time only, as after a suspend."""
        self._wall += timedelta(seconds=seconds)
