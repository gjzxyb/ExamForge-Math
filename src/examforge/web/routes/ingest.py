"""题目录入路由:GET 表单 + POST 端到端管线。"""

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ..deps import get_session_dep, problem_repo_dep, llm_dep, embedder_dep, config_dep
from ..app import templates
from ...models import SubjectArea
from ...pipeline import ingest_problem, run_pipeline


router = APIRouter()


@router.get("/ingest", response_class=HTMLResponse)
async def form(request: Request):
    return templates.TemplateResponse(request, "ingest.html", {
        "areas": [a.value for a in SubjectArea],
        "message": None,
    })


@router.post("/ingest", response_class=HTMLResponse)
async def submit(
    request: Request,
    year: int = Form(...),
    region: str = Form(...),
    subject_area: str = Form(...),
    stem: str = Form(...),
    reference: str = Form(""),
    source: str = Form(""),
    s: Session = Depends(get_session_dep),
    p_repo=Depends(problem_repo_dep),
    llm=Depends(llm_dep),
    embedder=Depends(embedder_dep),
    cfg=Depends(config_dep),
):
    p = ingest_problem(
        stem_latex=stem, year=year, region=region,
        subject_area=subject_area, reference_solution=reference or None,
        source=source, repo=p_repo,
    )
    r = run_pipeline(p, session=s, llm=llm, embedder=embedder, config=cfg)
    msg = (
        f"题目 #{p.id} 已处理: "
        f"confirmed={len(r.confirmed)} · "
        f"suspicions={len(r.suspicions)} · "
        f"candidates_new={len(r.candidates_new)}"
    )
    return templates.TemplateResponse(request, "ingest.html", {
        "areas": [a.value for a in SubjectArea],
        "message": msg,
    })