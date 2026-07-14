"""Pipeline 步骤 4:Review(可疑项判定 + 审核动作)。

第一版策略:只审可疑项(spec §5.④)。
- LLM 提出的方法不在 taxonomy → 可疑
- 相似度落在中间模糊带 → 可疑
- LLM 自报低置信 → 可疑(若 config.auto_confirm_min_confidence 不满足)
- 一题方法数超阈值 → 可疑
- 其余 → 自动 confirmed。
"""

from typing import Optional
from ..models import ReviewStatus, SolutionInstance, Method, MethodStatus, SubjectArea
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


def revise_method(
    si_id: int,
    method_id: int,
    *,
    solution_repo: SolutionRepo,
    method_repo: Optional[MethodRepo] = None,
    promote_method_to_confirmed: bool = True,
) -> SolutionInstance:
    si = solution_repo.get(si_id)
    if si is None:
        from .errors import NotInReviewQueue
        raise NotInReviewQueue(f"no SolutionInstance {si_id}")
    si.method_id = method_id
    si.review_status = ReviewStatus.CONFIRMED
    solution_repo.update(si)

    # 管理员在审核队列中改归并到某个 candidate 方法时，说明该方法已被认可；
    # 同步提升为 confirmed，才能出现在“方法库/报告”的已确认视图中。
    if method_repo is not None and promote_method_to_confirmed:
        m = method_repo.get(method_id)
        if m is not None and m.status == MethodStatus.CANDIDATE:
            m.status = MethodStatus.CONFIRMED
            method_repo.update(m)
    return si


def approve_as_new_method(
    si_id: int,
    *,
    name: str,
    subject_area: str,
    applicability: str = "",
    core_idea: str = "",
    key_theorem: str = "",
    secondary_theorems: str = "",
    procedure_steps: str = "",
    author_thinking_analysis: str = "",
    pitfalls: str = "",
    solution_repo: SolutionRepo,
    method_repo: MethodRepo,
    problem_repo,
    note: str = "manual-approve-new",
) -> SolutionInstance:
    """把 LLM 提名的"新方法"手动入库:创建 Method(confirmed),再把 SI 挂上去 + confirmed。

    重名检查:若同板块+同名已存在,直接挂到那个方法(避免重复创建)。
    SubjectArea 不可信:若 LLM 输出枚举外值,从 problem 自身板块回退。
    """
    from .errors import NotInReviewQueue
    si = solution_repo.get(si_id)
    if si is None:
        raise NotInReviewQueue(f"no SolutionInstance {si_id}")

    # SubjectArea 解析,失败 → 从 problem 拿
    try:
        area = SubjectArea(subject_area)
    except ValueError:
        problem = problem_repo.get(si.problem_id)
        if problem is not None:
            area = problem.subject_area
        else:
            area = SubjectArea.OTHER

    # 重名检查
    existing = method_repo.find_by_name(name, area)
    if existing is not None:
        # 复用已有方法；若审核时补充了定理信息,同步补到已有方法。
        changed = False
        if key_theorem and not getattr(existing, "key_theorem", ""):
            existing.key_theorem = key_theorem
            changed = True
        if secondary_theorems and not getattr(existing, "secondary_theorems", ""):
            existing.secondary_theorems = secondary_theorems
            changed = True
        if author_thinking_analysis and not getattr(existing, "author_thinking_analysis", ""):
            existing.author_thinking_analysis = author_thinking_analysis
            changed = True
        if changed:
            method_repo.update(existing)
        si.method_id = existing.id
        si.review_status = ReviewStatus.CONFIRMED
        si.reviewer_note = f"{note};复用已有方法 id={existing.id}"
        solution_repo.update(si)
        return si

    # 新建方法,直接 confirmed
    new_method = Method(
        name=name,
        subject_area=area,
        applicability=applicability or "(管理员未填)",
        core_idea=core_idea,
        key_theorem=key_theorem,
        secondary_theorems=secondary_theorems,
        procedure_steps=procedure_steps,
        author_thinking_analysis=author_thinking_analysis,
        pitfalls=pitfalls,
        status=MethodStatus.CONFIRMED,
    )
    method_repo.add(new_method)
    si.method_id = new_method.id
    si.review_status = ReviewStatus.CONFIRMED
    si.reviewer_note = note
    solution_repo.update(si)
    return si
