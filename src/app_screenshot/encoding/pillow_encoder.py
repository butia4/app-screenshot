"""Pillow adapter: downscale, then WebP (JPEG fallback when WebP is unavailable)."""

import io

from PIL import Image, ImageStat, features

from app_screenshot.encoding.ports import RawFrame
from app_screenshot.shared.notifier import Notifier


class PillowEncoder:
    def __init__(self, max_width: int, quality: int, notifier: Notifier) -> None:
        self._max_width = max_width
        self._quality = quality
        self._notifier = notifier
        if features.check("webp"):
            self.fmt, self.ext = "webp", "webp"
        else:
            self.fmt, self.ext = "jpeg", "jpg"
            notifier.notify("warn", "WebP is not available in Pillow; falling back to JPEG.")

    @staticmethod
    def _image(frame: RawFrame) -> Image.Image:
        return Image.frombytes("RGB", (frame.width, frame.height), frame.rgb)

    def luma_stddev(self, frame: RawFrame) -> float:
        small = self._image(frame).convert("L").resize((64, 64))
        return float(ImageStat.Stat(small).stddev[0])

    def encode(self, frame: RawFrame) -> bytes:
        img = self._image(frame)
        if img.width > self._max_width:
            height = max(1, round(img.height * self._max_width / img.width))
            img = img.resize((self._max_width, height), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        if self.fmt == "webp":
            img.save(buf, "WEBP", quality=self._quality, method=4)
        else:
            img.save(buf, "JPEG", quality=self._quality)
        return buf.getvalue()
