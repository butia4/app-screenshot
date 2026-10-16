import sys
from datetime import datetime
from pathlib import Path

from app_screenshot.cli import EXIT_CONFIG, EXIT_PLATFORM, format_banner, main
from app_screenshot.config.settings import build_config
from app_screenshot.shared.layout import SessionLayout


def test_banner_content(tmp_path):
    cfg = build_config({"output_root": str(tmp_path)})
    layout = SessionLayout(Path(tmp_path), "pc", datetime(2026, 1, 1, 9, 0, 0))
    banner = format_banner(cfg, layout, "webp")
    assert "BEING RECORDED" in banner
    assert str(layout.session_dir) in banner
    assert "every 60s" in banner and "every 1800s" in banner and "webp" in banner
    assert "Ctrl+C" in banner


def test_quality_zero_exits_2_and_creates_nothing(tmp_path, capsys):
    code = main(["--quality", "0", "--output", str(tmp_path / "out")])
    assert code == EXIT_CONFIG
    assert "quality" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_wayland_exits_3_and_creates_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    code = main(["--output", str(tmp_path / "out")])
    assert code == EXIT_PLATFORM
    assert "Wayland" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


class _FakeMss:
    closed = False

    def close(self):
        self.closed = True


def _wire_run(monkeypatch, tmp_path, *, stop_in_recovery):
    """Patch the edges of cli._run; returns an event log of what happened and in what order."""
    log: list = []
    mss = _FakeMss()
    monkeypatch.setattr("app_screenshot.capture.platform_guard.check_platform", lambda env: None)
    monkeypatch.setattr("app_screenshot.capture.mss_capturer.MssCapturer", lambda: mss)

    def fake_install(stop, notifier):
        log.append("handlers")
        log.append(stop)
        return lambda: log.append("restored")

    monkeypatch.setattr("app_screenshot.capture.signals.install_stop_handlers", fake_install)

    def fake_recovery_run(self, host_dir):
        log.append("recovery")
        if stop_in_recovery:
            log[1].set()

    monkeypatch.setattr("app_screenshot.archiving.recovery.Recovery.run", fake_recovery_run)
    monkeypatch.setattr(
        "app_screenshot.cli.format_banner", lambda *a, **k: log.append("banner") or "banner"
    )

    def fake_session_run(self):
        log.append("session")
        return 0

    monkeypatch.setattr("app_screenshot.capture.session.CaptureSession.run", fake_session_run)
    return log, mss


def test_stop_during_recovery_skips_session_and_exits_zero(tmp_path, monkeypatch):
    log, mss = _wire_run(monkeypatch, tmp_path, stop_in_recovery=True)
    assert main(["--output", str(tmp_path / "out")]) == 0
    assert "session" not in log and "restored" in log and mss.closed


def test_handlers_installed_before_banner_and_recovery(tmp_path, monkeypatch):
    log, mss = _wire_run(monkeypatch, tmp_path, stop_in_recovery=False)
    assert main(["--output", str(tmp_path / "out")]) == 0
    names = [e for e in log if isinstance(e, str)]
    assert names == ["handlers", "banner", "recovery", "session", "restored"]
    assert mss.closed


def test_mss_is_created_before_pillow_is_imported(tmp_path, monkeypatch):
    log, mss = _wire_run(monkeypatch, tmp_path, stop_in_recovery=True)
    for name in [m for m in sys.modules if m == "PIL" or m.startswith("PIL.")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.delitem(sys.modules, "app_screenshot.encoding.pillow_encoder", raising=False)
    pillow_seen_at_mss_creation: list[bool] = []

    def make_mss():
        pillow_seen_at_mss_creation.append("PIL" in sys.modules)
        return mss

    monkeypatch.setattr("app_screenshot.capture.mss_capturer.MssCapturer", make_mss)
    assert main(["--output", str(tmp_path / "out")]) == 0
    assert pillow_seen_at_mss_creation == [False]
    assert "PIL" in sys.modules  # and Pillow was imported afterwards


def test_interrupt_before_handlers_closes_capturer_and_exits_zero(tmp_path, monkeypatch):
    log, mss = _wire_run(monkeypatch, tmp_path, stop_in_recovery=False)

    def interrupted(stop, notifier):
        raise KeyboardInterrupt

    monkeypatch.setattr("app_screenshot.capture.signals.install_stop_handlers", interrupted)
    assert main(["--output", str(tmp_path / "out")]) == 0
    assert mss.closed and "session" not in log and "restored" not in log
