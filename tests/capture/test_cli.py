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
