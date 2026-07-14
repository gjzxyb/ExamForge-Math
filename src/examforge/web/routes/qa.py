"""学生问答路由:GET 表单 + POST 触发 RAG。"""

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func
from sqlmodel import Session

from ..deps import get_session_dep, llm_dep, embedder_dep, config_dep
from ..app import templates
from ...models import Method, MethodStatus, SolutionInstance, ReviewStatus, Problem
from ...qa import answer as qa_answer


router = APIRouter()


def _to_optional_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _qa_context(session: Session, selected_method_id: int | None = None) -> dict:
    """问答页上下文：方法库方法 + confirmed 例题选项。"""
    methods = list(session.execute(select(Method)).scalars().all())
    method_options = []
    for method in methods:
        count = session.execute(
            select(func.count(SolutionInstance.id)).where(
                SolutionInstance.method_id == method.id,
                SolutionInstance.review_status == ReviewStatus.CONFIRMED,
            )
        ).scalar_one()
        method_options.append({
            "id": method.id,
            "name": method.name,
            "subject_area": method.subject_area.value,
            "status": method.status.value,
            "count": int(count or 0),
        })
    status_order = {MethodStatus.CONFIRMED.value: 0, MethodStatus.SEED.value: 1, MethodStatus.CANDIDATE.value: 2}
    method_options.sort(key=lambda m: (-m["count"], status_order.get(m["status"], 9), m["subject_area"], m["name"]))

    sis = list(session.execute(
        select(SolutionInstance).where(SolutionInstance.review_status == ReviewStatus.CONFIRMED)
    ).scalars().all())
    example_options = []
    for si in sis:
        method = session.get(Method, si.method_id)
        problem = session.get(Problem, si.problem_id)
        if method is None or problem is None:
            continue
        summary = (si.transfer_note or si.key_steps or problem.stem_latex or "")[:48]
        example_options.append({
            "problem_id": problem.id,
            "method_id": method.id,
            "method_name": method.name,
            "year": problem.year,
            "region": problem.region,
            "summary": summary,
            "sub_knowledge": problem.sub_knowledge,
        })
    example_options.sort(key=lambda e: (e["method_id"], -(e["year"] or 0), e["problem_id"]))
    selected_method_id = selected_method_id or None
    visible_example_count = sum(1 for e in example_options if selected_method_id is None or e["method_id"] == selected_method_id)
    return {
        "methods": method_options,
        "examples": example_options,
        "visible_example_count": visible_example_count,
    }


@router.get("/qa", response_class=HTMLResponse)
async def view(
    request: Request,
    method_id: str = "",
    problem_id: str = "",
    s: Session = Depends(get_session_dep),
):
    selected_method_id = _to_optional_int(method_id)
    selected_problem_id = _to_optional_int(problem_id)
    context = _qa_context(s, selected_method_id)
    return templates.TemplateResponse(request, "qa.html", {
        **context,
        "answer": None,
        "question": "",
        "selected_method_id": selected_method_id,
        "selected_problem_id": selected_problem_id,
    })


@router.post("/qa", response_class=HTMLResponse)
async def submit(
    request: Request,
    question: str = Form(...),
    method_id: str = Form(""),
    problem_id: str = Form(""),
    s: Session = Depends(get_session_dep),
    llm=Depends(llm_dep),
    embedder=Depends(embedder_dep),
    cfg=Depends(config_dep),
):
    selected_method_id = _to_optional_int(method_id)
    selected_problem_id = _to_optional_int(problem_id)
    res = qa_answer(
        question,
        session=s,
        llm=llm,
        embedder=embedder,
        config=cfg,
        method_id=selected_method_id,
        problem_id=selected_problem_id,
    )
    context = _qa_context(s, selected_method_id)
    return templates.TemplateResponse(request, "qa.html", {
        **context,
        "answer": {
            "answer": res.answer,
            "cited_method_names": res.cited_method_names,
            "cited_problem_ids": res.cited_problem_ids,
        },
        "question": question,
        "selected_method_id": selected_method_id,
        "selected_problem_id": selected_problem_id,
    })
