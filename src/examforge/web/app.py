"""FastAPI 应用入口。"""

from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func

from ..models import Problem, Method, SolutionInstance, MethodStatus, ReviewStatus
from ..config.settings import init_settings_store
from .deps import ensure_init, get_session_dep, get_session


BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))


def _stats() -> dict:
    s = get_session()
    return {
        "problems": s.exec(select(func.count(Problem.id))).one(),
        "methods_total": s.exec(select(func.count(Method.id))).one(),
        "methods_confirmed": s.exec(
            select(func.count(Method.id)).where(Method.status == MethodStatus.CONFIRMED)
        ).one(),
        "pending_reviews": s.exec(
            select(func.count(SolutionInstance.id)).where(
                SolutionInstance.review_status == ReviewStatus.DRAFT,
            )
        ).one(),
        "confirmed_instances": s.exec(
            select(func.count(SolutionInstance.id)).where(
                SolutionInstance.review_status == ReviewStatus.CONFIRMED,
            )
        ).one(),
    }


def create_app(data_dir: Path) -> FastAPI:
    ensure_init(data_dir)
    init_settings_store(data_dir)  # 加载持久化设置
    app = FastAPI(title="ExamForge-Math")
    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
    app.state.data_dir = data_dir
    app.state.templates = templates

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