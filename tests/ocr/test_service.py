import pytest

from examforge.ocr import OCRError, recognize_math_image
from examforge.config.settings import OCRSettings
from examforge.ocr import service
from examforge.ocr.service import (
    _aliyun_endpoint_host,
    _extract_text,
    _is_aliyun_official_endpoint,
)


def test_mock_ocr_returns_latex_text():
    out = recognize_math_image(b"image", filename="a.png", provider="mock")
    assert out.provider == "mock"
    assert "f(x)" in out.latex_text


def test_none_ocr_is_user_friendly_error():
    with pytest.raises(OCRError) as e:
        recognize_math_image(b"image", provider="none")
    assert "OCR 未启用" in str(e.value)


def test_aliyun_official_endpoint_detection():
    endpoint = "https://ocr-api.cn-hangzhou.aliyuncs.com"
    assert _is_aliyun_official_endpoint(endpoint)
    assert _is_aliyun_official_endpoint("ocr-api.aliyuncs.com")
    assert not _is_aliyun_official_endpoint("https://ocr.example.com/proxy")
    assert _aliyun_endpoint_host(endpoint) == "ocr-api.cn-hangzhou.aliyuncs.com"


def test_extract_text_decodes_aliyun_data_json_string():
    data = {"Data": '{"content": "函数 $f(x)=x^2$"}'}
    assert _extract_text(data) == "函数 $f(x)=x^2$"


def test_official_aliyun_endpoint_uses_signed_sdk_path(monkeypatch):
    settings = OCRSettings(
        provider="aliyun",
        access_key_id="ak",
        access_key_secret="sk",
        endpoint="https://ocr-api.cn-hangzhou.aliyuncs.com",
    )
    monkeypatch.setattr(service, "_settings_for", lambda provider: settings)
    called = {}

    def fake_official(image_bytes, **kwargs):
        called["image"] = image_bytes
        called.update(kwargs)
        return {"Data": '{"content": "识别结果 $x^2$"}'}

    monkeypatch.setattr(service, "_recognize_aliyun_official", fake_official)
    monkeypatch.setattr(
        service,
        "_recognize_proxy",
        lambda *args, **kwargs: pytest.fail("官方 Endpoint 不应走代理协议"),
    )

    result = recognize_math_image(b"image", provider="aliyun")

    assert result.latex_text == "识别结果 $x^2$"
    assert called["image"] == b"image"
    assert called["endpoint"] == settings.endpoint
