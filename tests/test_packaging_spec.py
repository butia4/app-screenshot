from pathlib import Path

SPEC = Path(__file__).parent.parent / "packaging" / "app-screenshot.spec"


def test_spec_lists_webp_hidden_imports():
    text = SPEC.read_text()
    assert '"PIL.WebPImagePlugin"' in text and '"PIL._webp"' in text
