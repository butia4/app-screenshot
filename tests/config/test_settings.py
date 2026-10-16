import pytest

from app_screenshot.config.loader import load_config
from app_screenshot.config.settings import GIB, ConfigError, build_config, parse_size


def test_defaults():
    cfg = build_config({})
    assert cfg.capture_interval == 60
    assert cfg.archive_interval == 1800
    assert cfg.quality == 75
    assert cfg.max_width == 1920
    assert cfg.max_archive_size == 5 * GIB
    assert cfg.min_free_disk == GIB


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("5GB", 5 * GIB), ("500MB", 500 * 1024**2), ("1G", GIB), (1024, 1024), ("0", 0)],
)
def test_parse_size(raw, expected):
    assert parse_size("k", raw) == expected


@pytest.mark.parametrize("raw", ["abc", "5XB", -1, True, 1.5])
def test_parse_size_rejects(raw):
    with pytest.raises(ConfigError):
        parse_size("k", raw)


@pytest.mark.parametrize(
    ("values", "key"),
    [
        ({"quality": 0}, "quality"),
        ({"quality": 101}, "quality"),
        ({"capture_interval": 0}, "capture_interval"),
        ({"capture_interval": -5}, "capture_interval"),
        ({"capture_interval": 120, "archive_interval": 60}, "archive_interval"),
        ({"max_width": 10}, "max_width"),
        ({"max_archive_size": "-1"}, "max_archive_size"),
        ({"quality": "high"}, "quality"),
        ({"quality": True}, "quality"),
        ({"bogus": 1}, "bogus"),
    ],
)
def test_invalid_values_name_the_key(values, key):
    with pytest.raises(ConfigError, match=key):
        build_config(values)


def test_valid_overrides():
    cfg = build_config({"quality": 50, "capture_interval": 10, "output_root": "/tmp/x"})
    assert cfg.quality == 50
    assert cfg.capture_interval == 10
    assert str(cfg.output_root) == "/tmp/x"


def test_failure_limit_default_and_validation():
    assert build_config({}).failure_limit == 10
    assert build_config({"failure_limit": 3}).failure_limit == 3
    with pytest.raises(ConfigError, match="failure_limit"):
        build_config({"failure_limit": 0})


def test_output_root_defaults_to_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert build_config({}).output_root == tmp_path / "ScreenCaptures"


def test_relative_output_root_resolves_against_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert build_config({"output_root": "caps"}).output_root == tmp_path / "caps"


@pytest.mark.parametrize("key", ["capture_interval", "archive_interval"])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_numbers_are_rejected(key, bad):
    with pytest.raises(ConfigError, match=f"{key}.*finite"):
        build_config({key: bad})


@pytest.mark.parametrize("literal", ["nan", "inf", "-inf"])
def test_non_finite_toml_values_are_rejected(tmp_path, literal):
    toml = tmp_path / "c.toml"
    toml.write_text(f"capture_interval = {literal}\n")
    with pytest.raises(ConfigError, match="capture_interval"):
        load_config(["--config", str(toml)])


def test_non_finite_cli_interval_is_rejected():
    with pytest.raises(ConfigError, match="capture_interval"):
        load_config(["--interval", "nan"])


@pytest.mark.parametrize("key", ["capture_interval", "archive_interval"])
def test_interval_floor_is_one_second(key):
    with pytest.raises(ConfigError, match=key):
        build_config({key: 0.5})
    cfg = build_config({"capture_interval": 1.0, "archive_interval": 1.0})
    assert getattr(cfg, key) == 1.0


def test_zero_max_archive_size_is_rejected():
    with pytest.raises(ConfigError, match="max_archive_size"):
        build_config({"max_archive_size": 0})
