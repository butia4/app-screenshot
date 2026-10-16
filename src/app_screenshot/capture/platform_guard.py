"""Startup platform check: Wayland (and a missing X display) are unsupported."""

import sys
from collections.abc import Mapping


def check_platform(env: Mapping[str, str], platform: str | None = None) -> str | None:
    """Return an error message when capture cannot work here, else None."""
    if not (platform or sys.platform).startswith("linux"):
        return None
    if env.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        return (
            "Wayland sessions are not supported. Log in to an X11 session "
            "(e.g. choose 'Xorg' on the login screen) and try again."
        )
    if not env.get("DISPLAY"):
        return "No X11 display found (DISPLAY is not set). An X11 desktop session is required."
    return None
