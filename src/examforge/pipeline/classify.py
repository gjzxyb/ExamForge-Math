"""Pipeline 步骤 3:Classify(归类 + 发现新方法)。"""

from dataclasses import dataclass
from typing import Optional
from ..models import (
    Problem, Method, MethodStatus, ReviewStatus, SubjectArea, SolutionInstance,
)
from ..embedding import Embedder
from ..repositories import MethodRepo, VectorRepo
from ..config import PipelineConfig
from ..llm.schemas import ProposedMethodUse


@dataclass
class ClassifyResult:
    si: SolutionInstance
    action: str  # 'exact' / 'candidate' / 'suspicious'
    suggested_method_id: Optional[int]
    similarity: Optional[float]
    is_new_method: bool
    proposed_name: Optional[str] = None


def _cosine(a: list[float], b: list[float]) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def classify(
    problem: Problem,
    draft: SolutionInstance,
    *,
    method_repo: MethodRepo,
    embedder: Embedder,
    vector_repo: VectorRepo,
    config: PipelineConfig,
) -> ClassifyResult:
    """对单条 draft 决策应归到哪个 Method/或创建候选/或可疑。"""
    item = ProposedMethodUse.model_validate_json(draft.llm_raw)
    proposed_name = item.method_name
    proposed_area_str = item.subject_area or str(problem.subject_area.value)
    proposed_area = SubjectArea(proposed_area_str)

    # 步骤 A:精确命中
    exact = method_repo.find_by_name(proposed_name, proposed_area)
    if exact is not None:
        draft.method_id = exact.id
        return ClassifyResult(
            si=draft, action="exact", suggested_method_id=exact.id,
            similarity=None, is_new_method=False, proposed_name=proposed_name,
        )

    # 步骤 B:嵌入相似度兜底
    vec = embedder.embed(f"{proposed_name} {item.key_steps or ''}")
    candidates = (
        method_repo.list_confirmed_by_area(proposed_area)
        + method_repo.list_by_area(proposed_area, MethodStatus.SEED)
    )
    if not candidates:
        # 库为空 → 直接置为 candidate
        m = method_repo.add(Method(
            name=proposed_name, subject_area=proposed_area,
            applicability=item.applicability or "",
            core_idea="", procedure_steps="", pitfalls="",
            status=MethodStatus.CANDIDATE,
        ))
        draft.method_id = m.id
        return ClassifyResult(
            si=draft, action="candidate", suggested_method_id=m.id,
            similarity=None, is_new_method=True, proposed_name=proposed_name,
        )

    best_id = None
    best_score = -1.0
    for cm in candidates:
        ref_vec = embedder.embed(f"{cm.name} {cm.applicability}")
        score = _cosine(vec, ref_vec)
        if score > best_score:
            best_score = score
            best_id = cm.id

    if best_score >= config.similarity_high:
        draft.method_id = best_id
        return ClassifyResult(
            si=draft, action="candidate", suggested_method_id=best_id,
            similarity=float(best_score), is_new_method=False,
            proposed_name=proposed_name,
        )
    if best_score <= config.similarity_low:
        m = method_repo.add(Method(
            name=proposed_name, subject_area=proposed_area,
            applicability=item.applicability or "",
            core_idea="", procedure_steps="", pitfalls="",
            status=MethodStatus.CANDIDATE,
        ))
        draft.method_id = m.id
        return ClassifyResult(
            si=draft, action="candidate", suggested_method_id=m.id,
            similarity=float(best_score), is_new_method=True,
            proposed_name=proposed_name,
        )
    # 中间带 → 可疑
    draft.method_id = best_id or 0
    return ClassifyResult(
        si=draft, action="suspicious", suggested_method_id=best_id,
        similarity=float(best_score), is_new_method=False,
        proposed_name=proposed_name,
    )