import pytest

from examforge.ocr import OCRError, recognize_math_image


def test_mock_ocr_returns_latex_text():
    out = recognize_math_image(b"image", filename="a.png", provider="mock")
    assert out.provider == "mock"
    assert "f(x)" in out.latex_text


def test_none_ocr_is_user_friendly_error():
    with pytest.raises(OCRError) as e:
        recognize_math_image(b"image", provider="none")
    assert "OCR 未启用" in str(e.value)
