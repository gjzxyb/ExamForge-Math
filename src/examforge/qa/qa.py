"""应用 B · 学生问答(RAG)。

绝对不写库。检索 → 拼装方法知识 → LLM 回答。
"""

import math
from typing import Optional
from sqlmodel import Session
from sqlalchemy import select

from ..models import Method, MethodStatus, SolutionInstance, ReviewStatus, Problem, SubjectArea
from ..llm import LLM, QAResult
from ..embedding import Embedder
from ..repositories import vector_repo as get_vector_repo
from ..repositories import MethodRepo, SolutionRepo, ProblemRepo
from ..config import PipelineConfig


def _method_doc(method: Method, examples: list[dict]) -> str:
    ex_text = "\n".join(
        f"- (id={e['id']}, {e['year']} {e['region']}) {e['summary']}"
        for e in examples
    )
    return (
        f"方法名:{method.name}\n"
        f"适用:{method.applicability}\n"
        f"思想:{method.core_idea}\n"
        f"步骤:{method.procedure_steps}\n"
        f"坑:{method.pitfalls}\n"
        f"例题:\n{ex_text}"
    )


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def _example_rows(session: Session, method_id: int) -> list[dict]:
    sis = SolutionRepo(session).list_confirmed_by_method(method_id)
    out: list[dict] = []
    for si in sis:
        p = ProblemRepo(session).get(si.problem_id)
        if p is None:
            continue
        out.append({
            "id": p.id, "year": p.year, "region": p.region,
            "summary": (si.transfer_note or si.key_steps)[:60],
        })
    return out


def answer(
    question: str,
    *,
    session: Session,
    llm: LLM,
    embedder: Embedder,
    config: PipelineConfig,
    top_k: int = 3,
) -> QAResult:
    """对问题/题目做检索 + 回答,绝不写库。"""
    v_repo = get_vector_repo()
    q_vec = embedder.embed(question)
    hits = v_repo.query(q_vec, top_k=top_k)

    if not hits:
        return llm.answer_question(
            question=question, method_doc="(无相关方法库匹配)", examples=[],
        )

    # 取 confirmed 方法列表,按与问题的相似度排序
    stmt = select(Method).where(Method.status == MethodStatus.CONFIRMED)
    methods = list(session.execute(stmt).scalars().all())
    if not methods:
        return llm.answer_question(
            question=question, method_doc="(无 confirmed 方法)", examples=[],
        )

    ranked = sorted(
        methods,
        key=lambda m: _cosine(embedder.embed(f"{m.name} {m.applicability}"), q_vec),
        reverse=True,
    )[:top_k]
    top_method = ranked[0]
    examples = _example_rows(session, top_method.id)
    method_doc = _method_doc(top_method, examples)
    return llm.answer_question(
        question=question, method_doc=method_doc, examples=examples,
    )