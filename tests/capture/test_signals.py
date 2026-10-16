import signal
import threading

from app_screenshot.capture.signals import install_stop_handlers
from tests.fakes.notifier import FakeNotifier


def test_sigterm_sets_stop_and_restores():
    stop = threading.Event()
    before = signal.getsignal(signal.SIGTERM)
    restore = install_stop_handlers(stop, FakeNotifier())
    try:
        signal.raise_signal(signal.SIGTERM)
        assert stop.is_set()
        assert signal.getsignal(signal.SIGTERM) == signal.SIG_DFL  # second signal = hard exit
    finally:
        restore()
    assert signal.getsignal(signal.SIGTERM) == before
