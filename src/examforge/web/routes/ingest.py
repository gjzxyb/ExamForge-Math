"""题目录入路由:GET 表单 + POST 端到端管线。"""

from fastapi import APIRouter, Request, Form, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from sqlmodel import Session
from pathlib import Path
from uuid import uuid4

from ..deps import get_session_dep, problem_repo_dep, llm_dep, embedder_dep, config_dep
from ..app import templates
from ...models import SubjectArea
from ...pipeline import ingest_problem, run_pipeline


router = APIRouter()


async def _save_figure_upload(request: Request, figure: UploadFile | None) -> str | None:
    """保存题图/几何图截图,返回可被浏览器访问的 /uploads/... 路径。"""
    if figure is None or not figure.filename:
        return None
    suffix = Path(figure.filename).suffix.lower() or ".png"
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        suffix = ".png"
    uploads_dir: Path = request.app.state.uploads_dir
    target = uploads_dir / f"problem-{uuid4().hex}{suffix}"
    content = await figure.read()
    if not content:
        return None
    target.write_bytes(content)
    return f"/uploads/{target.name}"


@router.get("/ingest", response_class=HTMLResponse)
async def form(request: Request):
    return templates.TemplateResponse(request, "ingest.html", {
        "areas": [a.value for a in SubjectArea],
        "message": None,
        "extra_warning": None,
    })


@router.post("/ingest/ocr")
async def recognize_formula_image(
    provider: str = Form(""),
    figure: UploadFile = File(...),
):
    """上传题图/公式图,先调用 OCR 返回 LaTeX 文本,不入库。"""
    from ...ocr import OCRError, recognize_math_image

    content = await figure.read()
    try:
        result = recognize_math_image(
            content,
            filename=figure.filename or "upload.png",
            provider=provider or None,
        )
        return JSONResponse({
            "ok": True,
            "provider": result.provider,
            "latex_text": result.latex_text,
            "raw": result.raw,
        })
    except OCRError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=200)
    except Exception as e:
        return JSONResponse({
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
        }, status_code=200)


@router.post("/ingest", response_class=HTMLResponse)
async def submit(
    request: Request,
    year: int = Form(...),
    region: str = Form(...),
    subject_area: str = Form(...),
    stem: str = Form(...),
    figure: UploadFile | None = File(None),
    answer: str = Form(""),
    official_analysis_steps: str = Form(""),
    sub_knowledge: str = Form(""),
    problem_type_tags: str = Form(""),
    ocr_provider: str = Form("none"),
    reference: str = Form(""),
    source: str = Form(""),
    s: Session = Depends(get_session_dep),
    p_repo=Depends(problem_repo_dep),
    llm=Depends(llm_dep),
    embedder=Depends(embedder_dep),
    cfg=Depends(config_dep),
):
    try:
        image_ref = await _save_figure_upload(request, figure)
        # LLM 仍读取 reference_solution;优先使用官方解析步骤,兼容旧的 reference 字段。
        reference_solution = official_analysis_steps or reference or None
        p = ingest_problem(
            stem_latex=stem, year=year, region=region,
            subject_area=subject_area, reference_solution=reference_solution,
            answer=answer or None,
            official_analysis_steps=official_analysis_steps or reference or None,
            sub_knowledge=sub_knowledge,
            problem_type_tags=problem_type_tags,
            image_ref=image_ref,
            source=source, repo=p_repo,
        )
        r = run_pipeline(p, session=s, llm=llm, embedder=embedder, config=cfg)
    except Exception as e:
        # 兜底:管线任何阶段抛错都返 200 + 错误消息,避免 500
        import traceback
        tb = traceback.format_exc()
        return templates.TemplateResponse(request, "ingest.html", {
            "areas": [a.value for a in SubjectArea],
            "message": None,
            "extra_warning": (
                f"<b>管线失败</b>:{type(e).__name__}: {e}<br>"
                f"<details><summary>详细堆栈(给开发者)</summary>"
                f"<pre style='max-height:20em;overflow:auto'>{tb}</pre></details>"
                f"<br><small>请到 <a href='/settings'>设置</a> 检查 LLM/Embedder 配置,"
                f"或直接联系开发者贴这段信息。</small>"
            ),
        })

    backend = getattr(llm, "effective_backend", "unknown")
    msg = (
        f"题目 #{p.id} 已处理: "
        f"confirmed={len(r.confirmed)} · "
        f"suspicions={len(r.suspicions)} · "
        f"candidates_new={len(r.candidates_new)} · "
        f"LLM=[{r.llm_backend_used}]"
    )
    if image_ref:
        msg += " · 已保存题图"
    if ocr_provider != "none":
        msg += f" · OCR来源={ocr_provider}"
    extra_warning = ""
    if r.llm_error:
        extra_warning = (
            f"⚠ LLM 真实 API 调用失败,已降级为 mock。<br>"
            f"<small>错误:{r.llm_error[:300]}</small><br>"
            f"<small>请到 <a href=\"/settings\">设置</a> 修正后重新提交。</small>"
        )
    elif r.llm_backend_used == "mock":
        extra_warning = (
            "ℹ 当前 LLM 后端为 <b>mock</b>(测试占位),未调用真实 API。<br>"
            "<small>要在 ingest 时调用 DeepSeek 分析,请到 "
            "<a href=\"/settings\">设置</a> 填入 API key 并把后端切到 http。</small>"
        )
    return templates.TemplateResponse(request, "ingest.html", {
        "areas": [a.value for a in SubjectArea],
        "message": msg,
        "extra_warning": extra_warning,
    })