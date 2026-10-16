import io

import pytest
from PIL import Image, features

from app_screenshot.encoding.pillow_encoder import PillowEncoder
from app_screenshot.encoding.ports import RawFrame
from tests.fakes.notifier import FakeNotifier


def frame(w, h, color=(10, 200, 30)):
    return RawFrame(w, h, bytes(color) * (w * h))


def decode(data):
    return Image.open(io.BytesIO(data))


def test_downscales_preserving_aspect():
    enc = PillowEncoder(1920, 75, FakeNotifier())
    assert decode(enc.encode(frame(3840, 2160))).size == (1920, 1080)


def test_no_upscale():
    enc = PillowEncoder(1920, 75, FakeNotifier())
    assert decode(enc.encode(frame(1600, 900))).size == (1600, 900)


@pytest.mark.skipif(not features.check("webp"), reason="webp unavailable")
def test_webp_when_available():
    enc = PillowEncoder(1920, 75, FakeNotifier())
    assert (enc.fmt, enc.ext) == ("webp", "webp")
    assert decode(enc.encode(frame(640, 480))).format == "WEBP"


def test_jpeg_fallback_warns_once(monkeypatch):
    monkeypatch.setattr(features, "check", lambda name: False)
    n = FakeNotifier()
    enc = PillowEncoder(1920, 75, n)
    assert (enc.fmt, enc.ext) == ("jpeg", "jpg")
    assert decode(enc.encode(frame(640, 480))).format == "JPEG"
    enc.encode(frame(640, 480))
    assert len(n.messages("warn")) == 1


def test_luma_stddev_uniform_vs_noisy():
    enc = PillowEncoder(1920, 75, FakeNotifier())
    assert enc.luma_stddev(frame(200, 200)) < 2.0
    half = bytes([0, 0, 0]) * 20000 + bytes([255, 255, 255]) * 20000
    assert enc.luma_stddev(RawFrame(200, 200, half)) > 50


@pytest.mark.skipif(not features.check("webp"), reason="webp unavailable")
def test_webp_wider_than_format_limit_is_downscaled_and_stays_webp():
    enc = PillowEncoder(20000, 75, FakeNotifier())
    img = decode(enc.encode(frame(20000, 100)))
    assert img.format == "WEBP"
    assert max(img.size) <= 16383
    assert img.width == 16383 and abs(img.height - 100 * 16383 / 20000) <= 1


@pytest.mark.skipif(not features.check("webp"), reason="webp unavailable")
def test_webp_within_limits_is_unchanged():
    enc = PillowEncoder(20000, 75, FakeNotifier())
    assert decode(enc.encode(frame(16383, 50))).size == (16383, 50)
