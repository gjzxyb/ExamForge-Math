"""审核队列路由:GET 列表 + 三个 POST 动作端点 + JSON 辅助。"""

import json
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session
from sqlalchemy import select

from ..deps import (
    get_session_dep, solution_repo_dep, method_repo_dep, problem_repo_dep,
    embedder_dep,
)
from ..app import templates
from ...models import SolutionInstance, ReviewStatus, Problem, Method, SubjectArea
from ...pipeline.review import (
    confirm as pipeline_confirm,
    reject as pipeline_reject,
    revise_method as pipeline_revise,
    approve_as_new_method as pipeline_approve_new,
)
from ...pipeline.commit import commit_solution
from ...repositories import vector_repo as vector_repo_factory


def _commit_reviewed_solution(si, *, embedder, m_repo, s_repo) -> str:
    """审核动作确认后立即写入方法样本向量，确保方法库/问答可用。"""
    if si.review_status != ReviewStatus.CONFIRMED:
        return si.embedding_id or ""
    return commit_solution(
        si,
        embedder=embedder,
        vector_repo=vector_repo_factory(),
        method_repo=m_repo,
        solution_repo=s_repo,
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
        # 从 llm_raw 解析出 LLM 原始输出(method_name / subject_area / confidence)
        llm_method_name = None
        llm_subject_area = None
        llm_confidence = None
        try:
            raw = json.loads(si.llm_raw) if si.llm_raw else {}
            llm_method_name = raw.get("method_name")
            llm_subject_area = raw.get("subject_area")
            llm_confidence = raw.get("confidence")
        except Exception:
            pass
        items.append({
            "si": si,
            "problem": p,
            # 实际挂上的 method(可能为 None,因为 candidate 还在待审)
            "method_id": si.method_id,
            "method_name": m.name if m else None,
            "llm_method_name": llm_method_name,
            "llm_subject_area": llm_subject_area,
            "llm_confidence": llm_confidence,
        })
    return templates.TemplateResponse(request, "review_queue.html", {
        "items": items,
        "areas": [a.value for a in SubjectArea],
    })


@router.post("/review/{si_id}/confirm")
async def do_confirm(
    si_id: int,
    s_repo=Depends(solution_repo_dep),
    m_repo=Depends(method_repo_dep),
    embedder=Depends(embedder_dep),
):
    si = pipeline_confirm(si_id, note="manual-confirm",
                          solution_repo=s_repo, method_repo=m_repo)
    _commit_reviewed_solution(si, embedder=embedder, m_repo=m_repo, s_repo=s_repo)
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
    m_repo=Depends(method_repo_dep),
    embedder=Depends(embedder_dep),
):
    si = pipeline_revise(
        si_id, method_id=method_id, solution_repo=s_repo, method_repo=m_repo,
    )
    _commit_reviewed_solution(si, embedder=embedder, m_repo=m_repo, s_repo=s_repo)
    return RedirectResponse("/review", status_code=303)


@router.post("/review/{si_id}/approve_new")
async def do_approve_new(
    si_id: int,
    name: str = Form(...),
    subject_area: str = Form(...),
    applicability: str = Form(""),
    core_idea: str = Form(""),
    key_theorem: str = Form(""),
    secondary_theorems: str = Form(""),
    procedure_steps: str = Form(""),
    author_thinking_analysis: str = Form(""),
    pitfalls: str = Form(""),
    s_repo=Depends(solution_repo_dep),
    m_repo=Depends(method_repo_dep),
    p_repo=Depends(problem_repo_dep),
    embedder=Depends(embedder_dep),
):
    """把 SI 提名的"新方法"手动入库(管理员填描述)。"""
    si = pipeline_approve_new(
        si_id,
        name=name,
        subject_area=subject_area,
        applicability=applicability,
        core_idea=core_idea,
        key_theorem=key_theorem,
        secondary_theorems=secondary_theorems,
        procedure_steps=procedure_steps,
        author_thinking_analysis=author_thinking_analysis,
        pitfalls=pitfalls,
        solution_repo=s_repo,
        method_repo=m_repo,
        problem_repo=p_repo,
    )
    _commit_reviewed_solution(si, embedder=embedder, m_repo=m_repo, s_repo=s_repo)
    return RedirectResponse("/review", status_code=303)


@router.get("/review/methods.json")
async def list_methods_json(
    request: Request,
    s: Session = Depends(get_session_dep),
):
    """返回所有方法(confirmed + seed + candidate),供审核页面 JS 用名字挑选。"""
    methods = list(s.execute(select(Method)).scalars().all())
    return JSONResponse([
        {
            "id": m.id,
            "name": m.name,
            "status": m.status.value,
            "subject_area": m.subject_area.value,
        }
        for m in methods
    ])
