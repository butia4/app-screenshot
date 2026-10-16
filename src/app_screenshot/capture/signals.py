"""Graceful-stop signal handlers. A second signal falls back to the default (hard exit)."""

import signal
import threading
from collections.abc import Callable

from app_screenshot.shared.notifier import Notifier


def _stop_signals() -> list[signal.Signals]:
    sigs = [signal.SIGINT, signal.SIGTERM]
    sigbreak = getattr(signal, "SIGBREAK", None)  # Windows only
    if sigbreak is not None:
        sigs.append(sigbreak)
    return sigs


def install_stop_handlers(stop: threading.Event, notifier: Notifier) -> Callable[[], None]:
    """Install handlers that set `stop`. Returns a function restoring the previous ones."""
    sigs = _stop_signals()
    previous = {sig: signal.getsignal(sig) for sig in sigs}

    def handler(signum: int, _frame: object) -> None:
        notifier.notify("info", "stop requested: finishing and archiving pending frames...")
        stop.set()
        for sig in sigs:  # a second signal terminates immediately; recovery repairs on restart
            signal.signal(sig, signal.SIG_DFL)

    for sig in sigs:
        signal.signal(sig, handler)

    def restore() -> None:
        for sig, old in previous.items():
            # getsignal returns None for a handler installed outside Python: use the default
            signal.signal(sig, signal.SIG_DFL if old is None else old)

    return restore
