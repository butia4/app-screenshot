import pytest

from app_screenshot.config.loader import load_config
from app_screenshot.config.settings import ConfigError


def write(tmp_path, text):
    p = tmp_path / "c.toml"
    p.write_text(text)
    return str(p)


def test_cli_beats_toml_beats_default(tmp_path):
    path = write(tmp_path, "capture_interval = 120\nquality = 50\n")
    cfg = load_config(["--config", path, "--interval", "30"])
    assert cfg.capture_interval == 30
    assert cfg.quality == 50
    assert cfg.max_width == 1920


def test_only_toml(tmp_path):
    cfg = load_config(["--config", write(tmp_path, "capture_interval = 120\n")])
    assert cfg.capture_interval == 120


def test_neither(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_config([]).capture_interval == 60


def test_missing_explicit_file_errors(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(["--config", str(tmp_path / "nope.toml")])


def test_unknown_key_errors(tmp_path):
    with pytest.raises(ConfigError, match="mystery"):
        load_config(["--config", write(tmp_path, "mystery = 1\n")])


def test_malformed_toml_reports_location(tmp_path):
    with pytest.raises(ConfigError, match="malformed TOML"):
        load_config(["--config", write(tmp_path, "quality = = 3\n")])


def test_cli_quality_zero_invalid():
    with pytest.raises(ConfigError, match="quality"):
        load_config(["--quality", "0"])


def test_failure_limit_flag_and_toml(tmp_path):
    path = write(tmp_path, "failure_limit = 4\n")
    assert load_config(["--config", path]).failure_limit == 4
    assert load_config(["--config", path, "--failure-limit", "2"]).failure_limit == 2
    with pytest.raises(ConfigError, match="failure_limit"):
        load_config(["--failure-limit", "0"])
