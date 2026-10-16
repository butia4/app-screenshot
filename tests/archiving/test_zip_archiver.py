import os
import zipfile

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
import pytest

from app_screenshot.archiving.zip_archiver import ZipArchiver


def test_build_stored_and_verify(tmp_path):
    a = tmp_path / "a.webp"
    a.write_bytes(b"aaaa")
    dest = tmp_path / "x.zip"
    z = ZipArchiver()
    z.build(dest, [a])
    with zipfile.ZipFile(dest) as zf:
        assert zf.infolist()[0].compress_type == zipfile.ZIP_STORED
    assert z.verify(dest, {"a.webp": 4})
    assert not z.verify(dest, {"a.webp": 5})
    assert not z.verify(dest, {"a.webp": 4, "b.webp": 1})
    assert z.read_index(dest) == {"a.webp": 4}


def test_corrupt_zip_fails_verification(tmp_path):
    a = tmp_path / "a.webp"
    a.write_bytes(b"x" * 100)
    dest = tmp_path / "x.zip"
    z = ZipArchiver()
    z.build(dest, [a])
    raw = bytearray(dest.read_bytes())
    raw[40] ^= 0xFF  # flip a payload byte
    dest.write_bytes(bytes(raw))
    assert not z.verify(dest, {"a.webp": 100})
    dest.write_bytes(b"garbage")
    assert not z.verify(dest, {"a.webp": 100})


def test_fsync_uses_a_writable_descriptor(tmp_path, monkeypatch):
    if fcntl is None:
        pytest.skip("POSIX only")
    modes = []
    real = os.fsync

    def spy(fd):
        modes.append(fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE)
        real(fd)

    monkeypatch.setattr("app_screenshot.archiving.zip_archiver.os.fsync", spy)
    a = tmp_path / "a.webp"
    a.write_bytes(b"aaaa")
    ZipArchiver().build(tmp_path / "x.zip", [a])
    assert modes and all(m != os.O_RDONLY for m in modes)


def test_matching_requires_same_size_and_crc(tmp_path):
    same, other, longer, absent = (tmp_path / n for n in ("same.webp", "other.webp", "l.webp", "n"))
    same.write_bytes(b"aaaa")
    other.write_bytes(b"bbbb")
    longer.write_bytes(b"cccc")
    dest = tmp_path / "x.zip"
    z = ZipArchiver()
    z.build(dest, [same, other, longer])
    other.write_bytes(b"bbbX")  # same name and size, different bytes
    longer.write_bytes(b"cccc+")  # different size
    loose = {"same.webp": same, "other.webp": other, "l.webp": longer}
    assert z.matching(dest, loose) == {"same.webp"}
    assert z.matching(tmp_path / "missing.zip", loose) == set()
    dest.write_bytes(b"garbage")
    assert z.matching(dest, loose) == set()
