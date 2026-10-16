from app_screenshot.encoding.ports import RawFrame


class FakeCapturer:
    def __init__(self, fail_first: int = 0, always_fail: bool = False) -> None:
        self.calls = 0
        self._fail_first = fail_first
        self._always_fail = always_fail

    def grab(self) -> RawFrame:
        self.calls += 1
        if self._always_fail or self.calls <= self._fail_first:
            raise RuntimeError("grab failed")
        return RawFrame(2, 2, bytes([self.calls % 256]) * 12)
