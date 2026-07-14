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
    # 报告页应展示方法库中的所有方法。
    # 旧逻辑只取 confirmed，空库或仅有 seed 方法时下拉框会空白；
    # 这里与“方法库”保持一致，同时用状态和 confirmed 例题数提示成熟度。
    methods = list(s.execute(select(Method)).scalars().all())
    methods_out = []
    for m in methods:
        c = s.execute(
            select(func.count(SolutionInstance.id)).where(
                SolutionInstance.method_id == m.id,
                SolutionInstance.review_status == ReviewStatus.CONFIRMED,
            )
        ).scalar_one()
        methods_out.append({
            "id": m.id,
            "name": m.name,
            "subject_area": m.subject_area,
            "status": m.status,
            "count": int(c or 0),
        })
    # 有 confirmed 例题的优先，其次 confirmed/seed/candidate，再按板块和名称排序。
    status_order = {MethodStatus.CONFIRMED: 0, MethodStatus.SEED: 1, MethodStatus.CANDIDATE: 2}
    methods_out.sort(key=lambda x: (
        -x["count"],
        status_order.get(x["status"], 9),
        x["subject_area"].value,
        x["name"],
    ))

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