"""方法库浏览路由:列表 + 详情。"""

from typing import Optional
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func
from sqlmodel import Session

from ..deps import get_session_dep
from ..app import templates
from ...models import Method, MethodStatus, SubjectArea, SolutionInstance, ReviewStatus, Problem


router = APIRouter()


@router.get("/methods", response_class=HTMLResponse)
async def list_view(
    request: Request,
    area: str = "",
    status: str = "",
    s: Session = Depends(get_session_dep),
):
    stmt = select(Method)
    if area:
        stmt = stmt.where(Method.subject_area == SubjectArea(area))
    if status:
        stmt = stmt.where(Method.status == MethodStatus(status))
    methods = list(s.execute(stmt).scalars().all())
    out = []
    for m in methods:
        count = s.exec(
            select(func.count(SolutionInstance.id)).where(
                SolutionInstance.method_id == m.id,
                SolutionInstance.review_status == ReviewStatus.CONFIRMED,
            )
        ).one()
        out.append({
            "id": m.id, "name": m.name, "subject_area": m.subject_area.value,
            "status": m.status.value, "count": count,
        })
    return templates.TemplateResponse(request, "methods_list.html", {
        "areas": [a.value for a in SubjectArea],
        "area": area, "status": status, "methods": out,
    })


@router.get("/methods/{method_id}", response_class=HTMLResponse)
async def detail_view(
    request: Request,
    method_id: int,
    s: Session = Depends(get_session_dep),
):
    method = s.get(Method, method_id)
    if method is None:
        return HTMLResponse("Method not found", status_code=404)
    sis = list(s.execute(
        select(SolutionInstance).where(
            SolutionInstance.method_id == method_id,
            SolutionInstance.review_status == ReviewStatus.CONFIRMED,
        )
    ).scalars().all())
    examples = []
    for si in sis:
        p = s.get(Problem, si.problem_id)
        if p is None:
            continue
        examples.append({
            "id": p.id, "year": p.year, "region": p.region,
            "summary": (si.transfer_note or si.key_steps)[:60],
        })
    return templates.TemplateResponse(request, "method_detail.html", {
        "method": method, "examples": examples,
    })