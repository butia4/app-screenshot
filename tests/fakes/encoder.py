from app_screenshot.encoding.ports import RawFrame


class FakeEncoder:
    fmt = "webp"
    ext = "webp"

    def __init__(self, stddev: float = 50.0) -> None:
        self.stddev = stddev
        self.encoded = 0

    def luma_stddev(self, frame: RawFrame) -> float:
        return self.stddev

    def encode(self, frame: RawFrame) -> bytes:
        self.encoded += 1
        return b"frame-" + frame.rgb[:8] + bytes([self.encoded % 256])
