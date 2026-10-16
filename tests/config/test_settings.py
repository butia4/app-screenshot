import pytest

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
