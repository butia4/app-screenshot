"""Clock port and its system implementation."""

import time
from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def monotonic(self) -> float: ...

    def now(self) -> datetime:
        """Aware local wall-clock time."""
        ...


class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def now(self) -> datetime:
        return datetime.now().astimezone()
