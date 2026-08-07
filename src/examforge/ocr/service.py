"""数学题/公式 OCR 统一服务。"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse
from typing import Any

import httpx

from ..config.settings import OCRSettings, get_settings
from .postprocess import format_math_ocr_text


class OCRError(RuntimeError):
    """OCR 调用失败时的用户友好异常。"""


@dataclass
class OCRResult:
    provider: str
    latex_text: str
    raw: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


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
        value = obj.strip()
        if value.startswith(("{", "[")):
            try:
                return _extract_text(json.loads(value))
            except json.JSONDecodeError:
                pass
        return value
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


def _extract_aliyun_layout_text(obj: Any) -> str:
    """依据阿里云词块坐标恢复行序，再合并仅由版宽造成的折行。"""
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except json.JSONDecodeError:
            return ""
    if not isinstance(obj, dict):
        return ""
    if "Data" in obj:
        nested = _extract_aliyun_layout_text(obj["Data"])
        if nested:
            return nested

    words = obj.get("prism_wordsInfo")
    if not isinstance(words, list) or not words:
        return ""

    positioned: list[tuple[int, int, str]] = []
    for item in words:
        if not isinstance(item, dict):
            continue
        word = str(item.get("word", "")).strip()
        pos = item.get("pos")
        if not word or not isinstance(pos, list) or not pos:
            continue
        points = [p for p in pos if isinstance(p, dict)]
        if not points:
            continue
        x = min(int(p.get("x", 0)) for p in points)
        y = min(int(p.get("y", 0)) for p in points)
        positioned.append((y, x, word))
    if not positioned:
        return ""

    rows: list[dict[str, Any]] = []
    for y, x, word in sorted(positioned):
        row = next((r for r in reversed(rows) if abs(y - r["y"]) <= 7), None)
        if row is None:
            rows.append({"y": y, "items": [(x, word)]})
        else:
            row["items"].append((x, word))

    physical_lines = [
        "".join(word for _, word in sorted(row["items"])).strip()
        for row in rows
    ]
    logical_lines: list[str] = []
    block_start = re.compile(r"^(?:\([1-9]\d*\)|[①-⑳]|[A-D][.、])")
    for index, line in enumerate(physical_lines):
        if not line:
            continue
        # 分式的包围框可能跨越题号行上方和下方，导致它被识别为独立行。
        # 仅将紧邻题号行前的分式归回该题，避免改变普通段落换行。
        if (
            "\\frac" in line
            and not re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", line)
            and not block_start.match(line)
            and index + 1 < len(physical_lines)
            and block_start.match(physical_lines[index + 1])
        ):
            target = physical_lines[index + 1]
            ratio_anchor = re.search(r"公比为(?=\s*的等比数列)", target)
            if ratio_anchor:
                insert_at = ratio_anchor.end()
                physical_lines[index + 1] = target[:insert_at] + line + target[insert_at:]
            else:
                physical_lines[index + 1] += line
            continue
        if not logical_lines or block_start.match(line):
            logical_lines.append(line)
        elif re.search(r"[。；.!?！？]$", logical_lines[-1]):
            logical_lines.append(line)
        else:
            logical_lines[-1] += line

    question_start = re.compile(r"^\(([1-9]\d*)\)")
    starts = [
        (index, int(match.group(1)))
        for index, line in enumerate(logical_lines)
        if (match := question_start.match(line))
    ]
    numbers = [number for _, number in starts]
    if len(starts) > 1 and len(numbers) == len(set(numbers)):
        prefix = logical_lines[: starts[0][0]]
        blocks = [
            (number, logical_lines[start:next_start])
            for (start, number), (next_start, _) in zip(
                starts,
                starts[1:] + [(len(logical_lines), 0)],
            )
        ]
        logical_lines = prefix + [
            line
            for _, block in sorted(blocks)
            for line in block
        ]
    return "\n".join(logical_lines)


def _mock_result(filename: str) -> OCRResult:
    sample = (
        "% mock OCR result from " + filename + "\n"
        "设函数 $f(x)=x^3-3x$, 若对任意实数 $x$, $f(x)\\ge -a$ 恒成立, 求 $a$ 的最大值。"
    )
    return OCRResult(
        provider="mock",
        latex_text=format_math_ocr_text(sample),
        raw={"mock": True},
        raw_text=sample,
    )


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


def _is_aliyun_official_endpoint(endpoint: str) -> bool:
    """判断是否为阿里云 OCR 官方接入点，而不是用户自建代理。"""
    parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
    host = (parsed.hostname or "").lower()
    return host == "ocr-api.aliyuncs.com" or (
        host.startswith("ocr-api.") and host.endswith(".aliyuncs.com")
    )


def _aliyun_endpoint_host(endpoint: str) -> str:
    parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
    return parsed.netloc or parsed.path


def _aliyun_error_message(exc: Exception) -> str:
    code = str(getattr(exc, "code", "") or "")
    message = str(getattr(exc, "message", "") or exc)
    if code == "InvalidVersion" or "InvalidVersion" in message:
        return (
            "阿里云 OCR API 版本无效。ExamForge 已固定使用官方版本 "
            "2021-07-07；请确认 Endpoint 为 "
            "https://ocr-api.cn-hangzhou.aliyuncs.com，且不要把 Action 填入 Region。"
        )
    detail = f"{code}: {message}" if code else message
    return f"阿里云 OCR 调用失败: {detail}"


def _recognize_aliyun_official(
    image_bytes: bytes,
    *,
    settings: OCRSettings,
    endpoint: str,
    timeout: float,
) -> dict[str, Any]:
    """用阿里云官方 2021-07-07 SDK 完成 V3/RPC 签名和试卷识别。"""
    if not settings.access_key_id or not settings.access_key_secret:
        raise OCRError("阿里云 OCR 直连需要填写 Access Key ID 和 Access Key Secret。")

    try:
        from alibabacloud_ocr_api20210707.client import Client as AliyunOCRClient
        from alibabacloud_ocr_api20210707.models import RecognizeEduPaperOcrRequest
        from alibabacloud_tea_openapi import models as open_api_models
        from alibabacloud_tea_util import models as util_models

        config = open_api_models.Config(
            access_key_id=settings.access_key_id,
            access_key_secret=settings.access_key_secret,
            endpoint=_aliyun_endpoint_host(endpoint),
        )
        client = AliyunOCRClient(config)
        request = RecognizeEduPaperOcrRequest(
            image_type="photo",
            subject="default",
            output_oricoord=False,
            body=image_bytes,
        )
        runtime = util_models.RuntimeOptions(
            connect_timeout=int(timeout * 1000),
            read_timeout=int(timeout * 1000),
        )
        response = client.recognize_edu_paper_ocr_with_options(request, runtime)
        body = response.body.to_map() if hasattr(response.body, "to_map") else response.body
        if not isinstance(body, dict):
            raise OCRError("阿里云 OCR 返回了无法解析的响应。")
        return body
    except OCRError:
        raise
    except Exception as exc:
        raise OCRError(_aliyun_error_message(exc)) from exc


def _recognize_proxy(
    image_bytes: bytes,
    *,
    filename: str,
    provider_name: str,
    settings: OCRSettings,
    endpoint: str,
    timeout: float,
) -> dict[str, Any]:
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
            return resp.json()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:300]
        if provider_name == "aliyun" and "InvalidVersion" in body:
            raise OCRError(_aliyun_error_message(exc)) from exc
        raise OCRError(f"OCR HTTP {exc.response.status_code}: {body}") from exc
    except OCRError:
        raise
    except Exception as exc:
        raise OCRError(f"OCR 调用失败: {type(exc).__name__}: {exc}") from exc


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
    if provider_name == "aliyun" and _is_aliyun_official_endpoint(endpoint):
        data = _recognize_aliyun_official(
            image_bytes, settings=settings, endpoint=endpoint, timeout=timeout
        )
    else:
        data = _recognize_proxy(
            image_bytes, filename=filename, provider_name=provider_name,
            settings=settings, endpoint=endpoint, timeout=timeout,
        )

    raw_text = _extract_text(data)
    if not raw_text:
        raise OCRError("OCR 返回成功但未找到 latex/text 字段,请检查代理返回结构。")
    layout_text = _extract_aliyun_layout_text(data) or raw_text
    return OCRResult(
        provider=provider_name,
        latex_text=format_math_ocr_text(layout_text),
        raw=data,
        raw_text=raw_text,
    )
