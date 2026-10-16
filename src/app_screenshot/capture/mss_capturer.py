"""mss adapter. Needs a display, so it is validated manually (see README)."""

import mss

from app_screenshot.encoding.ports import RawFrame


class MssCapturer:
    def __init__(self) -> None:
        # Must be created before any GUI toolkit is imported (Windows DPI awareness).
        self._sct = mss.mss()

    def grab(self) -> RawFrame:
        shot = self._sct.grab(self._sct.monitors[0])  # monitors[0] = whole virtual desktop
        return RawFrame(shot.width, shot.height, bytes(shot.rgb))

    def close(self) -> None:
        self._sct.close()
