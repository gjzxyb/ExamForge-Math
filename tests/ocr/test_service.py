import pytest

from examforge.ocr import OCRError, format_math_ocr_text, recognize_math_image
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

    assert result.latex_text == "识别结果$x^2$"
    assert result.raw_text == "识别结果 $x^2$"
    assert called["image"] == b"image"
    assert called["endpoint"] == settings.endpoint


def test_format_math_ocr_text_improves_exam_readability():
    raw = (
        "甲、乙两人进行乒乓球练习，每个球胜者得1分，负者得0分."
        "设每个球甲 胜的概率为 P \\left( \\frac { 1 } { 2 } < p < 1 \\right) ， ，"
        "乙胜的概率为 q，p+q=1， ，且各球的胜负相 互独立."
        "对正整数 k≥2， 记 p _ { k } 为打完k个球后甲比乙至少多得2分的概 率，"
        " qk 为打完k个球后乙比甲至少多得2分的概率. "
        "(1)求 p _ { 3 } ， p _ { 4 } (用p表示)；"
        "(2)若 \\frac { p _ { 4 } - p _ { 3 } } { q _ { 4 } - q _ { 3 } } = 4 ， ，求 "
        "(3)证明：对任意正整数 m，p2m+1-q2m+1<p2m-q2m<p2m+2-q2m+2"
    )

    formatted = format_math_ocr_text(raw)

    assert "甲胜的概率为$p$（$\\frac{1}{2}<p<1$）" in formatted
    assert "各球的胜负相互独立" in formatted
    assert "$p_k$" in formatted and "$q_k$" in formatted
    assert "\n(1) 求" in formatted
    assert "\n(2) 若" in formatted
    assert "\n(3) 证明" in formatted
    assert "$p_{2m+1}-q_{2m+1}<p_{2m}-q_{2m}<p_{2m+2}-q_{2m+2}$" in formatted
    assert "， ，" not in formatted
    assert "概 率" not in formatted
