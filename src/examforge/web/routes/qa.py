"""学生问答路由:GET 表单 + POST 触发 RAG。"""

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ..deps import get_session_dep, llm_dep, embedder_dep, config_dep
from ..app import templates
from ...qa import answer as qa_answer


router = APIRouter()


@router.get("/qa", response_class=HTMLResponse)
async def view(request: Request):
    return templates.TemplateResponse(request, "qa.html",
                                      {"answer": None, "question": ""})


@router.post("/qa", response_class=HTMLResponse)
async def submit(
    request: Request,
    question: str = Form(...),
    s: Session = Depends(get_session_dep),
    llm=Depends(llm_dep),
    embedder=Depends(embedder_dep),
    cfg=Depends(config_dep),
):
    res = qa_answer(question, session=s, llm=llm,
                    embedder=embedder, config=cfg)
    return templates.TemplateResponse(request, "qa.html", {
        "answer": {
            "answer": res.answer,
            "cited_method_names": res.cited_method_names,
            "cited_problem_ids": res.cited_problem_ids,
        },
        "question": question,
    })