"""审核队列路由:GET 列表 + 三个 POST 动作端点。"""

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from ..deps import get_session_dep, solution_repo_dep, method_repo_dep, problem_repo_dep
from ..app import templates
from ...models import SolutionInstance, ReviewStatus, Problem
from ...pipeline.review import (
    confirm as pipeline_confirm,
    reject as pipeline_reject,
    revise_method as pipeline_revise,
)


router = APIRouter()


@router.get("/review", response_class=HTMLResponse)
async def queue(
    request: Request,
    s: Session = Depends(get_session_dep),
    p_repo=Depends(problem_repo_dep),
    m_repo=Depends(method_repo_dep),
    s_repo=Depends(solution_repo_dep),
):
    drafts = s_repo.list_by_review_status(ReviewStatus.DRAFT)
    items = []
    for si in drafts:
        p = p_repo.get(si.problem_id)
        m = m_repo.get(si.method_id) if si.method_id else None
        items.append({
            "si": si,
            "problem": p,
            "method_name": m.name if m else "?",
            "similarity": None,
        })
    return templates.TemplateResponse(request, "review_queue.html", {"items": items})


@router.post("/review/{si_id}/confirm")
async def do_confirm(
    si_id: int,
    s_repo=Depends(solution_repo_dep),
    m_repo=Depends(method_repo_dep),
):
    pipeline_confirm(si_id, note="manual-confirm",
                     solution_repo=s_repo, method_repo=m_repo)
    return RedirectResponse("/review", status_code=303)


@router.post("/review/{si_id}/reject")
async def do_reject(
    si_id: int,
    note: str = Form(""),
    s_repo=Depends(solution_repo_dep),
):
    pipeline_reject(si_id, note=note, solution_repo=s_repo)
    return RedirectResponse("/review", status_code=303)


@router.post("/review/{si_id}/revise")
async def do_revise(
    si_id: int,
    method_id: int = Form(...),
    s_repo=Depends(solution_repo_dep),
):
    pipeline_revise(si_id, method_id=method_id, solution_repo=s_repo)
    return RedirectResponse("/review", status_code=303)