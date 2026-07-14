"""应用 B · 学生问答(RAG)。

绝对不写库。检索 → 拼装方法知识 → LLM 回答。
"""

import math
from sqlmodel import Session
from sqlalchemy import select

from ..models import Method, MethodStatus, SolutionInstance, ReviewStatus
from ..llm import LLM, QAResult
from ..embedding import Embedder
from ..repositories import vector_repo as get_vector_repo
from ..repositories import SolutionRepo, ProblemRepo
from ..config import PipelineConfig


def _method_doc(method: Method, examples: list[dict]) -> str:
    ex_lines: list[str] = []
    for e in examples:
        marker = "【当前选中例题】" if e.get("focus") else ""
        line = f"- {marker}(id={e['id']}, {e['year']} {e['region']}) {e['summary']}"
        if e.get("focus"):
            details = []
            if e.get("stem"):
                details.append(f"  题干:{str(e['stem'])[:500]}")
            if e.get("answer"):
                details.append(f"  答案:{e['answer']}")
            if e.get("official_analysis_steps"):
                details.append(f"  官方解析:{str(e['official_analysis_steps'])[:500]}")
            if e.get("key_steps"):
                details.append(f"  本方法关键步骤:{str(e['key_steps'])[:500]}")
            if e.get("transfer_note"):
                details.append(f"  迁移提示:{str(e['transfer_note'])[:300]}")
            if details:
                line = "\n".join([line, *details])
        ex_lines.append(line)
    ex_text = "\n".join(ex_lines)
    return (
        f"方法名:{method.name}\n"
        f"板块:{method.subject_area.value}\n"
        f"状态:{method.status.value}\n"
        f"适用:{method.applicability}\n"
        f"思想:{method.core_idea}\n"
        f"关键定理:{getattr(method, 'key_theorem', '')}\n"
        f"二级定理:{getattr(method, 'secondary_theorems', '')}\n"
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
            "id": p.id,
            "year": p.year,
            "region": p.region,
            "summary": (si.transfer_note or si.key_steps or p.stem_latex)[:120],
            "stem": p.stem_latex,
            "answer": p.answer,
            "official_analysis_steps": p.official_analysis_steps,
            "sub_knowledge": p.sub_knowledge,
            "problem_type_tags": p.problem_type_tags,
            "image_ref": p.image_ref,
            "key_steps": si.key_steps,
            "transfer_note": si.transfer_note,
        })
    return out


def _with_citations(result: QAResult, *, method: Method | None, problem_id: int | None) -> QAResult:
    """选择了明确上下文时，即使 LLM 未返回引用，也把上下文作为可核验引用补上。"""
    method_names = list(result.cited_method_names or [])
    if method is not None and method.name not in method_names:
        method_names.insert(0, method.name)
    problem_ids = list(result.cited_problem_ids or [])
    if problem_id is not None and problem_id not in problem_ids:
        problem_ids.insert(0, problem_id)
    return QAResult(
        answer=result.answer,
        cited_method_names=method_names,
        cited_problem_ids=problem_ids,
    )


def _selected_solution_context(
    session: Session,
    *,
    method_id: int | None,
    problem_id: int | None,
) -> tuple[Method | None, int | None, list[dict]]:
    """读取用户显式选择的方法/例题上下文；只读，不写库。"""
    method = session.get(Method, method_id) if method_id is not None else None
    if method is None and problem_id is not None:
        si = session.execute(
            select(SolutionInstance).where(
                SolutionInstance.problem_id == problem_id,
                SolutionInstance.review_status == ReviewStatus.CONFIRMED,
            )
        ).scalars().first()
        if si is not None:
            method = session.get(Method, si.method_id)

    if method is None:
        return None, None, []

    examples = _example_rows(session, method.id)
    selected_problem_id = None
    if problem_id is not None:
        for e in examples:
            if e["id"] == problem_id:
                e["focus"] = True
                selected_problem_id = problem_id
                break
    if selected_problem_id is not None:
        examples.sort(key=lambda e: (0 if e.get("focus") else 1, -(e.get("year") or 0), e.get("id") or 0))
    return method, selected_problem_id, examples


def answer(
    question: str,
    *,
    session: Session,
    llm: LLM,
    embedder: Embedder,
    config: PipelineConfig,
    top_k: int = 3,
    method_id: int | None = None,
    problem_id: int | None = None,
) -> QAResult:
    """对问题/题目做检索 + 回答,绝不写库。

    可选 method_id/problem_id 用于“指定方法/指定该方法下例题”提问；
    未指定时保持原来的 RAG 自动检索流程。
    """
    selected_method, selected_problem_id, selected_examples = _selected_solution_context(
        session, method_id=method_id, problem_id=problem_id,
    )
    if selected_method is not None:
        method_doc = _method_doc(selected_method, selected_examples)
        result = llm.answer_question(
            question=question, method_doc=method_doc, examples=selected_examples,
        )
        return _with_citations(result, method=selected_method, problem_id=selected_problem_id)

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
