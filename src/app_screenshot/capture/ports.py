"""Capture port."""

from typing import Protocol

from app_screenshot.encoding.ports import RawFrame


class Capturer(Protocol):
    def grab(self) -> RawFrame:
        """Grab the full virtual desktop. Raises on failure."""
        ...
