"""题目录入路由:GET 表单 + 后台端到端管线。"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from fastapi import APIRouter, Request, Form, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from sqlmodel import Session
from pathlib import Path
from uuid import uuid4

from ..deps import get_session_dep, problem_repo_dep, llm_dep, embedder_dep, config_dep
from ..app import templates
from ...models import Problem, SubjectArea
from ...pipeline import ingest_problem, run_pipeline


router = APIRouter()


@dataclass
class IngestJob:
    id: str
    problem_id: int
    status: str = "queued"
    stage: str = "题目已保存，等待后台管线"
    error: str = ""
    queued_count: int = 0
    llm_backend: str = ""
    created_at: str = ""
    finished_at: str = ""


_ingest_jobs: dict[str, IngestJob] = {}
_ingest_jobs_lock = Lock()


def _update_ingest_job(job_id: str, **values) -> None:
    with _ingest_jobs_lock:
        job = _ingest_jobs.get(job_id)
        if job is None:
            return
        for key, value in values.items():
            setattr(job, key, value)


def _run_ingest_job(job_id: str, problem_id: int) -> None:
    """在线程池中生成答案并运行管线，避免 HTTP 请求长时间悬挂。"""
    from ...config import get_config
    from ...embedding import get_embedder
    from ...llm import get_llm
    from ...repositories import get_engine

    session = Session(get_engine())
    try:
        problem = session.get(Problem, problem_id)
        if problem is None:
            raise RuntimeError(f"题目 #{problem_id} 不存在")

        llm = get_llm()
        answer = (problem.answer or "").strip()
        analysis = (problem.official_analysis_steps or "").strip()
        reference = (problem.reference_solution or "").strip()
        if not answer or not analysis:
            _update_ingest_job(job_id, status="running", stage="正在调用 API 生成详细答案")
            generated, warning, _ = _generate_missing_answer_fail_open(
                llm,
                stem_latex=problem.stem_latex,
                subject_area=problem.subject_area.value,
                reference_solution=reference or answer or None,
            )
            if not answer:
                answer = (generated.answer or "").strip()
            if not analysis:
                analysis = (generated.analysis_steps or "").strip() or reference or answer
            problem.answer = answer or None
            problem.official_analysis_steps = analysis or None
            problem.reference_solution = analysis or reference or answer or None
            session.add(problem)
            session.commit()
            session.refresh(problem)
            if warning:
                _update_ingest_job(job_id, stage="真实 API 失败，已保存兜底答案；正在提炼方法")

        _update_ingest_job(job_id, status="running", stage="答案已保存，正在提炼并分类解题方法")
        result = run_pipeline(
            problem,
            session=session,
            llm=llm,
            embedder=get_embedder(),
            config=get_config(),
            force_review=True,
        )
        _update_ingest_job(
            job_id,
            status="completed",
            stage="管线完成，答案与解析已进入审核队列",
            queued_count=len(result.suspicions),
            llm_backend=result.llm_backend_used,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:
        session.rollback()
        _update_ingest_job(
            job_id,
            status="failed",
            stage="后台管线执行失败",
            error=_friendly_llm_error(exc),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
    finally:
        session.close()


def _friendly_llm_error(exc: Exception) -> str:
    """把 LLM/API 异常压缩成前端可读消息。"""
    try:
        from ...llm.http_llm import LLMHttpError
        if isinstance(exc, LLMHttpError):
            return exc.as_user_message() or str(exc)
    except Exception:
        pass
    return f"{type(exc).__name__}: {exc}"


def _build_answer_search_query(*, stem_latex: str, subject_area: str) -> str:
    stem = " ".join((stem_latex or "").split())
    if len(stem) > 180:
        stem = stem[:180]
    return f"高中数学 {subject_area} 题目答案 详细解析 {stem}".strip()


def _format_answer_web_context(hits) -> str:
    lines: list[str] = []
    for idx, hit in enumerate(hits, start=1):
        title = (hit.title or "无标题").strip()
        snippet = (hit.snippet or "").strip()
        url = (hit.url or "").strip()
        block = [f"[{idx}] {title}"]
        if snippet:
            block.append(f"摘要: {snippet}")
        if url:
            block.append(f"URL: {url}")
        lines.append("\n".join(block))
    return "\n\n".join(lines)


def _get_answer_web_context(*, stem_latex: str, subject_area: str) -> tuple[str, str]:
    """为缺失答案生成准备搜索上下文;失败不阻断录入。"""
    try:
        from ...config.settings import get_settings
        from ...search import search_method_pages

        settings = get_settings().web_search
        if (settings.provider or "disabled").lower() == "disabled":
            return "", ""
        query = _build_answer_search_query(
            stem_latex=stem_latex, subject_area=subject_area,
        )
        hits = search_method_pages(query, settings, max_results=3)
        context = _format_answer_web_context(hits)
        if not context:
            return "", "全网搜索未返回可用摘要,已仅用题干生成答案。"
        return context, f"已调用全网搜索 API 辅助生成答案(provider={settings.provider}, hits={len(hits)})"
    except Exception as exc:
        return "", f"全网搜索 API 调用失败,已仅用题干生成答案:{_friendly_llm_error(exc)}"


def _generate_missing_answer_fail_open(
    llm,
    *,
    stem_latex: str,
    subject_area: str,
    reference_solution: str | None,
):
    """缺失答案时调用当前 LLM/API 生成详细答案；失败则降级 mock,不阻断录入。"""
    from ...llm.mock_llm import MockLLM

    web_context, search_notice = _get_answer_web_context(
        stem_latex=stem_latex, subject_area=subject_area,
    )
    try:
        generated = llm.generate_answer(
            stem_latex=stem_latex,
            subject_area=subject_area,
            reference_solution=reference_solution,
            web_context=web_context or None,
        )
        return generated, "", search_notice
    except Exception as exc:
        warning = _friendly_llm_error(exc)
        mock = MockLLM()
        mock.effective_backend = "mock_fallback"
        generated = mock.generate_answer(
            stem_latex=stem_latex,
            subject_area=subject_area,
            reference_solution=reference_solution,
            web_context=web_context or None,
        )
        return generated, warning, search_notice


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
        "generated_answer": None,
        "generated_answer_steps": None,
        "generated_answer_confidence": None,
        "queued_count": 0,
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
            "raw_text": result.raw_text,
            "raw": result.raw,
        })
    except OCRError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=200)
    except Exception as e:
        return JSONResponse({
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
        }, status_code=200)


@router.post("/ingest/start")
async def start_background_ingest(
    request: Request,
    background_tasks: BackgroundTasks,
    year: int = Form(...),
    region: str = Form(...),
    subject_area: str = Form(...),
    stem: str = Form(...),
    figure: UploadFile | None = File(None),
    answer: str = Form(""),
    official_analysis_steps: str = Form(""),
    sub_knowledge: str = Form(""),
    problem_type_tags: str = Form(""),
    reference: str = Form(""),
    source: str = Form(""),
    p_repo=Depends(problem_repo_dep),
):
    """先持久化题目并立即响应，耗时的 LLM/管线转入后台线程。"""
    image_ref = await _save_figure_upload(request, figure)
    answer = (answer or "").strip()
    official_analysis_steps = (official_analysis_steps or "").strip()
    reference = (reference or "").strip()
    problem = ingest_problem(
        stem_latex=stem,
        year=year,
        region=region,
        subject_area=subject_area,
        reference_solution=official_analysis_steps or reference or answer or None,
        answer=answer or None,
        official_analysis_steps=official_analysis_steps or None,
        sub_knowledge=sub_knowledge,
        problem_type_tags=problem_type_tags,
        image_ref=image_ref,
        source=source,
        repo=p_repo,
    )
    job_id = uuid4().hex
    job = IngestJob(
        id=job_id,
        problem_id=problem.id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    with _ingest_jobs_lock:
        _ingest_jobs[job_id] = job
    background_tasks.add_task(_run_ingest_job, job_id, problem.id)
    return JSONResponse(
        {
            "ok": True,
            "job_id": job_id,
            "problem_id": problem.id,
            "status_url": f"/ingest/jobs/{job_id}",
        },
        status_code=202,
    )


@router.get("/ingest/jobs/{job_id}")
async def get_ingest_job(job_id: str):
    with _ingest_jobs_lock:
        job = _ingest_jobs.get(job_id)
        payload = asdict(job) if job else None
    if payload is None:
        return JSONResponse({"ok": False, "error": "任务不存在或服务已重启"}, status_code=404)
    return JSONResponse({"ok": True, **payload})


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
    generated_answer = None
    generated_answer_steps = None
    generated_answer_confidence = None
    answer_generation_warning = ""
    answer_search_notice = ""
    try:
        image_ref = await _save_figure_upload(request, figure)
        # LLM 仍读取 reference_solution;优先使用人工填写的官方解析，兼容旧 reference 字段。
        answer = (answer or "").strip()
        official_analysis_steps = (official_analysis_steps or "").strip()
        reference = (reference or "").strip()
        generation_reference_parts = []
        if answer:
            generation_reference_parts.append(f"已知最终答案：\n{answer}")
        if official_analysis_steps:
            generation_reference_parts.append(f"人工填写的解析：\n{official_analysis_steps}")
        if reference:
            generation_reference_parts.append(f"补充参考：\n{reference}")
        generation_reference = "\n\n".join(generation_reference_parts) or None

        # 最终答案或详细解析任一缺失时都调用生成接口。此前只检查 answer，
        # 导致用户填写简答/旧 reference 后，生成的详细步骤没有被持久化。
        if not answer or not official_analysis_steps:
            generated, answer_generation_warning, answer_search_notice = _generate_missing_answer_fail_open(
                llm,
                stem_latex=stem,
                subject_area=subject_area,
                reference_solution=generation_reference,
            )
            generated_answer = (generated.answer or "").strip()
            generated_answer_steps = (generated.analysis_steps or "").strip()
            generated_answer_confidence = generated.confidence
            if generated_answer and not answer:
                answer = generated_answer
            if generated_answer_steps and not official_analysis_steps:
                official_analysis_steps = generated_answer_steps
            elif not official_analysis_steps:
                # 兼容少数只返回最终答案、不返回 analysis_steps 的模型。
                official_analysis_steps = reference or generated_answer or answer

        # reference_solution 是旧版兼容字段；新生成的详细解析应优先于简短参考答案。
        reference_solution = official_analysis_steps or reference or answer or None
        p = ingest_problem(
            stem_latex=stem, year=year, region=region,
            subject_area=subject_area, reference_solution=reference_solution,
            answer=answer or None,
            official_analysis_steps=official_analysis_steps or None,
            sub_knowledge=sub_knowledge,
            problem_type_tags=problem_type_tags,
            image_ref=image_ref,
            source=source, repo=p_repo,
        )
        r = run_pipeline(
            p, session=s, llm=llm, embedder=embedder, config=cfg,
            force_review=True,
        )
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
            "generated_answer": generated_answer,
            "generated_answer_steps": generated_answer_steps,
            "generated_answer_confidence": generated_answer_confidence,
            "queued_count": 0,
        })

    msg = (
        f"题目 #{p.id} 已处理: "
        f"confirmed={len(r.confirmed)} · "
        f"suspicions={len(r.suspicions)} · "
        f"candidates_new={len(r.candidates_new)} · "
        f"LLM=[{r.llm_backend_used}]"
    )
    queued_count = len(r.suspicions)
    if image_ref:
        msg += " · 已保存题图"
    if ocr_provider != "none":
        msg += f" · OCR来源={ocr_provider}"
    if answer_search_notice:
        msg += f" · {answer_search_notice}"
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
    if answer_generation_warning:
        answer_warning = (
            "⚠ 缺失答案自动生成时真实 API 调用失败,已用 mock 占位答案兜底。<br>"
            f"<small>错误:{answer_generation_warning[:300]}</small>"
        )
        extra_warning = f"{extra_warning}<hr>{answer_warning}" if extra_warning else answer_warning
    return templates.TemplateResponse(request, "ingest.html", {
        "areas": [a.value for a in SubjectArea],
        "message": msg,
        "extra_warning": extra_warning,
        "generated_answer": generated_answer,
        "generated_answer_steps": generated_answer_steps,
        "generated_answer_confidence": generated_answer_confidence,
        "queued_count": queued_count,
    })
