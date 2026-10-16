from pathlib import Path

from app_screenshot.retention.disk_guard import DiskGuard
from tests.fakes.notifier import FakeNotifier

GB = 1024**3


class FakeStorage:
    def __init__(self, free):
        self.free = free

    def free_bytes(self, p):
        if isinstance(self.free, Exception):
            raise self.free
        return self.free


def make(free):
    s, n = FakeStorage(free), FakeNotifier()
    return DiskGuard(s, n, Path("/x"), GB), s, n


def test_pause_once_and_resume_with_hysteresis():
    g, s, n = make(GB // 2)
    assert not g.ok()
    assert not g.ok()
    assert len(n.messages("warn")) == 1
    s.free = int(GB * 1.05)  # above min but below hysteresis
    assert not g.ok()
    s.free = 2 * GB
    assert g.ok()
    assert len(n.messages("info")) == 1


def test_unknown_free_warns_once_and_continues():
    g, _, n = make(OSError("nope"))
    assert g.ok() and g.ok()
    assert len(n.messages("warn")) == 1
