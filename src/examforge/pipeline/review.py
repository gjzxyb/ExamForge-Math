"""Pipeline 步骤 4:Review(可疑项判定 + 审核动作)。

第一版策略:只审可疑项(spec §5.④)。
- LLM 提出的方法不在 taxonomy → 可疑
- 相似度落在中间模糊带 → 可疑
- LLM 自报低置信 → 可疑(若 config.auto_confirm_min_confidence 不满足)
- 一题方法数超阈值 → 可疑
- 其余 → 自动 confirmed。
"""

from typing import Optional
from ..models import ReviewStatus, SolutionInstance, MethodStatus
from ..repositories import SolutionRepo, MethodRepo
from ..config import PipelineConfig


def is_suspicious(
    result_action: str,
    *,
    confidence: float,
    methods_count_for_problem: int,
    config: PipelineConfig,
) -> bool:
    if result_action == "suspicious":
        return True
    if result_action in ("candidate", "exact"):
        if methods_count_for_problem > config.max_methods_per_problem:
            return True
        if confidence < config.auto_confirm_min_confidence:
            return True
        return False
    return True


def auto_confirm_if_clean(si: SolutionInstance) -> bool:
    return si.review_status == ReviewStatus.CONFIRMED


def confirm(si_id: int, *, note: str, solution_repo: SolutionRepo,
            method_repo: Optional[MethodRepo] = None,
            promote_method_to_confirmed: bool = True) -> SolutionInstance:
    si = solution_repo.get(si_id)
    if si is None:
        from .errors import NotInReviewQueue
        raise NotInReviewQueue(f"no SolutionInstance {si_id}")
    si.review_status = ReviewStatus.CONFIRMED
    si.reviewer_note = note
    solution_repo.update(si)
    if method_repo is not None and promote_method_to_confirmed:
        m = method_repo.get(si.method_id)
        if m is not None and m.status == MethodStatus.CANDIDATE:
            m.status = MethodStatus.CONFIRMED
            method_repo.update(m)
    return si


def reject(si_id: int, *, note: str, solution_repo: SolutionRepo) -> SolutionInstance:
    si = solution_repo.get(si_id)
    if si is None:
        from .errors import NotInReviewQueue
        raise NotInReviewQueue(f"no SolutionInstance {si_id}")
    si.review_status = ReviewStatus.REJECTED
    si.reviewer_note = note
    solution_repo.update(si)
    return si


def revise_method(si_id: int, method_id: int, *, solution_repo: SolutionRepo) -> SolutionInstance:
    si = solution_repo.get(si_id)
    if si is None:
        from .errors import NotInReviewQueue
        raise NotInReviewQueue(f"no SolutionInstance {si_id}")
    si.method_id = method_id
    si.review_status = ReviewStatus.CONFIRMED
    solution_repo.update(si)
    return si