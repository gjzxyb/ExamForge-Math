"""数学题/公式 OCR 统一服务。"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..config.settings import OCRSettings, get_settings


class OCRError(RuntimeError):
    """OCR 调用失败时的用户友好异常。"""


@dataclass
class OCRResult:
    provider: str
    latex_text: str
    raw: dict[str, Any] = field(default_factory=dict)


def _normalize_provider(provider: str | None) -> str:
    p = (provider or "").strip().lower()
    aliases = {
        "": "",
        "none": "none",
        "mock": "mock",
        "tencent": "tencent",
        "tencent_math_ocr": "tencent",
        "aliyun": "aliyun",
        "aliyun_printed_formula_ocr": "aliyun",
    }
    return aliases.get(p, p)


def _extract_text(obj: Any) -> str:
    """从常见 OCR JSON 返回结构中尽量抽取 LaTeX/文本。"""
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj.strip()
    if isinstance(obj, list):
        parts = [_extract_text(x) for x in obj]
        return "\n".join([x for x in parts if x]).strip()
    if not isinstance(obj, dict):
        return ""

    # 常见扁平字段 / 自建代理字段
    for key in (
        "latex", "latex_text", "latexText", "text", "content", "result",
        "Result", "formula", "Formula", "recognizedText", "RecognizedText",
    ):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    # 常见嵌套字段
    for key in ("data", "Data", "response", "Response", "body", "Body", "output", "Output"):
        val = obj.get(key)
        text = _extract_text(val)
        if text:
            return text

    # 腾讯云 OCR 常见 TextDetections / 阿里云布局类数组
    for key in ("TextDetections", "textDetections", "elements", "Elements", "prism_wordsInfo"):
        val = obj.get(key)
        text = _extract_text(val)
        if text:
            return text

    for key in ("DetectedText", "Text", "Word", "word", "latex"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    return ""


def _mock_result(filename: str) -> OCRResult:
    sample = (
        "% mock OCR result from " + filename + "\n"
        "设函数 $f(x)=x^3-3x$, 若对任意实数 $x$, $f(x)\\ge -a$ 恒成立, 求 $a$ 的最大值。"
    )
    return OCRResult(provider="mock", latex_text=sample, raw={"mock": True})


def _settings_for(provider: str) -> OCRSettings:
    try:
        s = get_settings().ocr
    except RuntimeError:
        # CLI/单元测试未初始化 SettingsStore 时仍允许显式 provider 工作。
        s = OCRSettings()
    if provider in ("", "settings"):
        return s
    # 使用页面传入的 provider 临时覆盖 settings.provider,其它密钥/endpoint 仍走设置页。
    return OCRSettings(
        provider=provider,
        access_key_id=s.access_key_id,
        access_key_secret=s.access_key_secret,
        region=s.region,
        endpoint=s.endpoint,
    )


def _endpoint_for(settings: OCRSettings) -> str:
    endpoint = (settings.endpoint or "").strip()
    if endpoint:
        return endpoint
    # 不猜官方 Action。没有 endpoint 时给明确提示,避免静默打错云厂商 API。
    raise OCRError(
        "OCR endpoint 未配置。请在设置页填写已完成腾讯云/阿里云签名的代理地址,"
        "或选择 mock 做本地演示。"
    )


def _auth_headers(settings: OCRSettings) -> dict[str, str]:
    headers: dict[str, str] = {}
    if settings.access_key_id:
        headers["X-Access-Key-Id"] = settings.access_key_id
    if settings.access_key_secret:
        # 面向自建代理: 用 Bearer 传递密钥。若代理不需要可留空。
        headers["Authorization"] = f"Bearer {settings.access_key_secret}"
    if settings.region:
        headers["X-Region"] = settings.region
    return headers


def recognize_math_image(
    image_bytes: bytes,
    *,
    filename: str = "upload.png",
    provider: str | None = None,
    timeout: float = 60.0,
) -> OCRResult:
    """识别数学试题/公式图片并返回 LaTeX 文本。

    provider 可传 none/mock/tencent/aliyun 或表单别名;不传则使用 Settings.ocr.provider。
    """
    if not image_bytes:
        raise OCRError("未收到图片内容")

    settings = _settings_for(_normalize_provider(provider))
    provider_name = _normalize_provider(settings.provider)

    if provider_name in ("", "none"):
        raise OCRError("OCR 未启用。请选择 mock/tencent/aliyun,或在设置页配置 Provider。")
    if provider_name == "mock":
        return _mock_result(filename)
    if provider_name not in {"tencent", "aliyun"}:
        raise OCRError(f"未知 OCR provider: {settings.provider!r}")

    endpoint = _endpoint_for(settings)
    payload = {
        "provider": provider_name,
        "filename": filename,
        "image_base64": base64.b64encode(image_bytes).decode("ascii"),
        "return_format": "latex",
        "scene": "math_problem",
    }
    headers = {"Content-Type": "application/json", **_auth_headers(settings)}
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        raise OCRError(f"OCR HTTP {e.response.status_code}: {e.response.text[:300]}") from e
    except Exception as e:
        raise OCRError(f"OCR 调用失败: {type(e).__name__}: {e}") from e

    text = _extract_text(data)
    if not text:
        raise OCRError("OCR 返回成功但未找到 latex/text 字段,请检查代理返回结构。")
    return OCRResult(provider=provider_name, latex_text=text, raw=data)
