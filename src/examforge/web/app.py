"""FastAPI 应用入口。"""

import logging
import re
import traceback
from html import escape
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func

from ..models import Problem, Method, SolutionInstance, MethodStatus, ReviewStatus
from ..config.settings import init_settings_store
from .deps import ensure_init, get_session_dep, get_session


log = logging.getLogger("examforge.web")


BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))


_MATH_SECTION_LABELS = (
    "审题与条件整理", "关键转化与公式", "计算推导", "零点存在性与唯一性",
    "结果验证与取舍", "易错点", "全网搜索参考",
)


def _format_math_text(value: object) -> str:
    """把 LLM 生成的一整段解析整理成可读 HTML,并保留 MathJax 公式。

    真实模型偶尔会把“审题与条件整理：关键转化……”输出成一整段。
    这里在展示层做轻量分段,不改数据库原文。
    """
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return "—"
    for label in _MATH_SECTION_LABELS:
        text = re.sub(rf"(?<!^)(?<!\n)\s*({re.escape(label)}[:：])", r"\n\n\1", text)
    text = re.sub(r"(?<!^)(?<!\n)\s*(第\(\d+\)问[①②③④⑤]?[:：])", r"\n\n\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    html = escape(text)
    # 简单支持 Markdown 二级标题,其余保持换行,由 MathJax 渲染公式。
    html = re.sub(r"^##\s*(.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    return html.replace("\n", "<br>\n")


templates.env.filters["math_text"] = _format_math_text


def _stats() -> dict:
    s = get_session()
    return {
        "problems": s.exec(select(func.count(Problem.id))).scalar() or 0,
        "methods_total": s.exec(select(func.count(Method.id))).scalar() or 0,
        "methods_confirmed": s.exec(
            select(func.count(Method.id)).where(Method.status == MethodStatus.CONFIRMED)
        ).scalar() or 0,
        "pending_reviews": s.exec(
            select(func.count(SolutionInstance.id)).where(
                SolutionInstance.review_status == ReviewStatus.DRAFT,
            )
        ).scalar() or 0,
        "confirmed_instances": s.exec(
            select(func.count(SolutionInstance.id)).where(
                SolutionInstance.review_status == ReviewStatus.CONFIRMED,
            )
        ).scalar() or 0,
    }


def create_app(data_dir: Path) -> FastAPI:
    ensure_init(data_dir)
    init_settings_store(data_dir)  # 加载持久化设置
    app = FastAPI(title="ExamForge-Math")
    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
    uploads_dir = data_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")
    app.state.data_dir = data_dir
    app.state.uploads_dir = uploads_dir
    app.state.templates = templates

    @app.exception_handler(Exception)
    async def _all_exc_handler(request: Request, exc: Exception):
        """全局兜底:任何未处理异常 → 返 HTML 错误页 + 完整 traceback 到 stderr。

        行为:浏览器请求 HTML 时返可读错误页;其它(API/JSON)返 JSON。
        不吞 traceback,始终 dump 到 stderr 便于 uvicorn 日志查。
        """
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        tb_text = "".join(tb)
        log.error("Unhandled error on %s %s:\n%s",
                  request.method, request.url.path, tb_text)
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            body = (
                f"<html><head><meta charset='utf-8'><title>500</title>"
                f"<link rel='stylesheet' href='/static/style.css'></head>"
                f"<body><nav>← <a href='/'>返回首页</a></nav>"
                f"<h1>500 Internal Server Error</h1>"
                f"<p><b>路径:</b> {request.method} {request.url.path}</p>"
                f"<p><b>异常类型:</b> {type(exc).__name__}</p>"
                f"<p><b>异常消息:</b> {exc}</p>"
                f"<h3>Traceback</h3>"
                f"<pre>{tb_text}</pre>"
                f"</body></html>"
            )
            return HTMLResponse(body, status_code=500)
        return JSONResponse(
            {"error": type(exc).__name__, "message": str(exc),
             "traceback": tb_text}, status_code=500,
        )

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return templates.TemplateResponse(request, "index.html",
                                          {"stats": _stats()})

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    # 路由
    from .routes import ingest, methods as methods_route, review, report, qa, settings as settings_route
    app.include_router(ingest.router)
    app.include_router(methods_route.router)
    app.include_router(review.router)
    app.include_router(report.router)
    app.include_router(qa.router)
    app.include_router(settings_route.router)

    return app
