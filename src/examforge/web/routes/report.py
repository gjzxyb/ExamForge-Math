"""报告生成路由。"""

from typing import Optional
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func
from sqlmodel import Session

from ..deps import get_session_dep, llm_dep
from ..app import templates
from ...models import Method, MethodStatus, SubjectArea, SolutionInstance, ReviewStatus
from ...report import generate_report


router = APIRouter()


@router.get("/report", response_class=HTMLResponse)
async def view(
    request: Request,
    method_id: Optional[int] = None,
    s: Session = Depends(get_session_dep),
    llm=Depends(llm_dep),
):
    # 列表只显示 confirmed,以及至少有 1 道 confirmed 例题的
    methods = list(s.execute(
        select(Method).where(Method.status == MethodStatus.CONFIRMED)
    ).scalars().all())
    methods_out = []
    for m in methods:
        c = s.exec(
            select(func.count(SolutionInstance.id)).where(
                SolutionInstance.method_id == m.id,
                SolutionInstance.review_status == ReviewStatus.CONFIRMED,
            )
        ).one()
        methods_out.append({
            "id": m.id, "name": m.name, "subject_area": m.subject_area,
            "count": c,
        })
    # 没有 confirmed 例题的方法排到后面
    methods_out.sort(key=lambda x: -x["count"])

    report_md = None
    selected = method_id
    if method_id is not None:
        try:
            report_md = generate_report(method_id, session=s, llm=llm)
        except ValueError:
            report_md = None
    return templates.TemplateResponse(request, "report.html", {
        "methods": methods_out, "report": report_md, "selected": selected,
    })