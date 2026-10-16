import zipfile

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
