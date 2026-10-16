from app_screenshot.encoding.blank import BlankFrameMonitor
from tests.fakes.clock import FakeClock
from tests.fakes.notifier import FakeNotifier


def make(**kw):
    n, c = FakeNotifier(), FakeClock()
    return BlankFrameMonitor(n, c, **kw), n, c


def test_warns_after_three_uniform():
    m, n, _ = make()
    m.observe(0.0)
    m.observe(0.0)
    assert not n.events
    m.observe(0.0)
    assert len(n.messages("warn")) == 1


def test_normal_frame_resets_streak():
    m, n, _ = make()
    for v in (0, 0, 50, 0, 0):
        m.observe(v)
    assert not n.events


def test_rate_limited_then_warns_again():
    m, n, c = make(min_gap_s=600)
    for _ in range(6):
        m.observe(0.0)
    assert len(n.events) == 1
    c.advance(601)
    m.observe(0.0)
    assert len(n.events) == 2
