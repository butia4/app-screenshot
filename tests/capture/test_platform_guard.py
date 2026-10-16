import pytest

from app_screenshot.capture.platform_guard import check_platform


def test_wayland_rejected():
    msg = check_platform({"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":0"}, "linux")
    assert msg and "Wayland" in msg and "X11" in msg


def test_linux_without_display_rejected():
    assert check_platform({"XDG_SESSION_TYPE": "x11"}, "linux")


@pytest.mark.parametrize(
    ("env", "platform"),
    [
        ({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}, "linux"),
        ({"DISPLAY": ":0"}, "linux"),
        ({}, "win32"),
        ({}, "darwin"),
    ],
)
def test_allowed(env, platform):
    assert check_platform(env, platform) is None
