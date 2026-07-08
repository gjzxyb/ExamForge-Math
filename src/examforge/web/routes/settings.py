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
    base_url: str = Form(""),
    api_key: str = Form(""),
    model: str = Form(""),
    timeout: float = Form(60.0),
):
    get_settings_store().update(llm={
        "backend": backend,
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "timeout": timeout,
    })
    return JSONResponse({"ok": True, "redirect": "/settings?saved=llm"})


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


@router.post("/settings/ocr")
async def save_ocr(
    provider: str = Form("none"),
    access_key_id: str = Form(""),
    access_key_secret: str = Form(""),
    region: str = Form(""),
    endpoint: str = Form(""),
):
    """OCR 配置项仅占位,保存但不会触发任何调用。"""
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
    """对当前 LLM 配做一次最小请求(extract_solution 用 trivial prompt),
    成功 → 返 {ok:true, summary},失败 → {ok:false, error:用户友好消息}
    """
    from ...llm import get_llm
    from ...llm.schemas import ExtractedSolution
    from ...llm.http_llm import LLMHttpError
    try:
        llm = get_llm()
        out = llm.extract_solution(
            stem_latex="1+1",
            reference_solution="2",
            taxonomy_hint=[],
            subject_area="其他",
        )
        ExtractedSolution.model_validate(out.model_dump())
        return JSONResponse({
            "ok": True,
            "backend": get_settings().llm.backend,
            "method_count": len(out.methods),
        })
    except LLMHttpError as e:
        return JSONResponse({
            "ok": False, "error": e.as_user_message(), "status_code": e.status_code,
            "url": e.request_url,
        }, status_code=200)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=200)


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