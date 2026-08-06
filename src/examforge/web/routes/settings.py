"""设置路由:GET 展示 + POST 更新 + POST 测试连接。

LLM/Embedder 的「测试连接」调用真实 API 做最轻量的请求,
失败以 JSON 返错给前端渲染。
"""

import json
from typing import Optional
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from ..deps import get_session_dep  # noqa: F401  保留(可能后续需要)
from ...config.settings import get_settings_store, get_settings


router = APIRouter()


def _flash(request: Request, kind: str, msg: str) -> None:
    """简易 flash:存到 session 之类,这里直接放 query string。
    第一版简化:刷新后由后端 query 携带 flash。
    """
    pass  # 简化:前端用 URL ?saved=1 提示


@router.get("/settings", response_class=HTMLResponse)
async def view(request: Request, saved: Optional[str] = None, tested: Optional[str] = None):
    s = get_settings()
    return request.app.state.templates.TemplateResponse(
        request, "settings.html",
        {
            "s": s,
            "saved": saved,
            "tested": tested,
        },
    )


@router.post("/settings/llm")
async def save_llm(
    backend: str = Form("mock"),
    provider: str = Form("deepseek"),
    base_url: str = Form(""),
    api_key: str = Form(""),
    model: str = Form(""),
    thinking_mode: str = Form("auto"),
    timeout: float = Form(180.0),
):
    from ...llm.http_llm import effective_llm_timeout

    effective_timeout = effective_llm_timeout(timeout) if backend == "http" else timeout
    get_settings_store().update(llm={
        "backend": backend,
        "provider": provider,
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "thinking_mode": thinking_mode,
        "timeout": effective_timeout,
    })
    return JSONResponse({"ok": True, "redirect": "/settings?saved=llm"})


@router.post("/settings/model-control")
async def save_model_control(
    enabled: bool = Form(False),
    agent_md: str = Form(""),
    skills_enabled: bool = Form(False),
    skills_md: str = Form(""),
):
    """保存全局模型约束与 Skill 指令。

    这些内容会在真实 LLM 调用时追加到 system prompt，用于统一约束
    模型行为、输出风格和可用技能流程。
    """
    get_settings_store().update(model_control={
        "enabled": enabled,
        "agent_md": agent_md,
        "skills_enabled": skills_enabled,
        "skills_md": skills_md,
    })
    return JSONResponse({"ok": True, "redirect": "/settings?saved=model-control"})


@router.post("/settings/embedder")
async def save_embedder(
    backend: str = Form("mock"),
    base_url: str = Form(""),
    api_key: str = Form(""),
    model: str = Form(""),
    dim: int = Form(1024),
    timeout: float = Form(30.0),
):
    get_settings_store().update(embedder={
        "backend": backend,
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "dim": dim,
        "timeout": timeout,
    })
    return JSONResponse({"ok": True, "redirect": "/settings?saved=embedder"})




@router.post("/settings/web-search")
async def save_web_search(
    provider: str = Form("mock"),
    endpoint: str = Form(""),
    api_key: str = Form(""),
    timeout: float = Form(20.0),
):
    """保存全网搜索 API 配置,用于方法库发现外部方法。"""
    get_settings_store().update(web_search={
        "provider": provider,
        "endpoint": endpoint,
        "api_key": api_key,
        "timeout": timeout,
    })
    return JSONResponse({"ok": True, "redirect": "/settings?saved=web-search"})


@router.post("/settings/ocr")
async def save_ocr(
    provider: str = Form("none"),
    access_key_id: str = Form(""),
    access_key_secret: str = Form(""),
    region: str = Form(""),
    endpoint: str = Form(""),
):
    """保存 OCR 配置；阿里云官方 Endpoint 将自动使用 2021-07-07 API。"""
    get_settings_store().update(ocr={
        "provider": provider,
        "access_key_id": access_key_id,
        "access_key_secret": access_key_secret,
        "region": region,
        "endpoint": endpoint,
    })
    return JSONResponse({"ok": True, "redirect": "/settings?saved=ocr"})


# ---------- 测试连接 ----------------------------------------------------

@router.post("/settings/test-llm")
async def test_llm():
    """快速验证端点、鉴权、模型名称和 JSON Output 协议。"""
    import time
    from ...llm import get_llm
    from ...llm.http_llm import CONNECTION_PROBE_TIMEOUT, LLMHttpError

    configured_backend = get_settings().llm.backend
    started = time.perf_counter()
    try:
        llm = get_llm()
        effective_backend = getattr(llm, "effective_backend", configured_backend)
        if configured_backend == "http" and not str(effective_backend).startswith("http"):
            return JSONResponse({
                "ok": False,
                "backend": effective_backend,
                "configured_backend": configured_backend,
                "error": "LLM 配置为 http,但实际已降级为 mock。请检查 API Key、Base URL 和模型名称后再测试。",
            }, status_code=200)

        probe_ok = True
        if str(effective_backend).startswith("http"):
            probe_ok = llm.probe_connection() == {"ok": True}
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return JSONResponse({
            "ok": probe_ok,
            "backend": effective_backend,
            "configured_backend": configured_backend,
            "probe_ok": probe_ok,
            "probe_mode": "quick",
            "probe_timeout": CONNECTION_PROBE_TIMEOUT,
            "elapsed_ms": elapsed_ms,
        })
    except LLMHttpError as e:
        return JSONResponse({
            "ok": False,
            "error": e.as_user_message(),
            "status_code": e.status_code,
            "url": e.request_url,
            "backend": configured_backend,
        }, status_code=200)
    except Exception as e:
        return JSONResponse({
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "backend": configured_backend,
        }, status_code=200)


@router.post("/settings/test-embedder")
async def test_embedder():
    try:
        from ...embedding import get_embedder
        e = get_embedder()
        vec = e.embed("ping")
        return JSONResponse({
            "ok": True,
            "backend": get_settings().embedder.backend,
            "dim": len(vec),
        })
    except Exception as ex:
        return JSONResponse({"ok": False, "error": str(ex)}, status_code=200)
