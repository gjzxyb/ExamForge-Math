"""应用 A · 教师报告生成。

只读 confirmed 数据。方法节点已有结构化字段,LLM 负责润色成 Markdown 友好的章节。
"""

from sqlmodel import Session
from ..repositories import MethodRepo, SolutionRepo, ProblemRepo
from ..llm import LLM


def _example_rows(session: Session, method_id: int) -> list[dict]:
    sis = SolutionRepo(session).list_confirmed_by_method(method_id)
    out: list[dict] = []
    for si in sis:
        p = ProblemRepo(session).get(si.problem_id)
        if p is None:
            continue
        out.append({
            "year": p.year,
            "region": p.region,
            "id": p.id,
            "summary": (si.transfer_note or si.key_steps)[:60],
        })
    return out


def generate_report(
    method_id: int,
    *,
    session: Session,
    llm: LLM,
) -> str:
    m_repo = MethodRepo(session)
    method = m_repo.get(method_id)
    if method is None:
        raise ValueError(f"no Method {method_id}")
    examples = _example_rows(session, method_id)
    sections = llm.render_report(
        method_name=method.name,
        applicability=method.applicability,
        core_idea=method.core_idea,
        procedure=method.procedure_steps,
        pitfalls=method.pitfalls,
        examples=examples,
    )
    return _to_markdown(method.name, sections, len(examples))


def _to_markdown(name: str, s, n: int) -> str:
    return f"""# {name} 解法专题报告

> 共 {n} 道 confirmed 例题

## 引入
{s.intro}

## 核心思想
{s.core_idea}

## 适用特征
{s.applicability}

## 通用步骤
{s.procedure}

## 常见坑
{s.pitfalls}

## 典型例题
{s.examples_markdown}
"""