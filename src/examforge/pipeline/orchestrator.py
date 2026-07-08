"""端到端管线编排。"""

from dataclasses import dataclass, field
import warnings
from sqlmodel import Session
from ..models import (
    Problem, ReviewStatus, MethodStatus,
)
from ..repositories import (
    ProblemRepo, MethodRepo, SolutionRepo, vector_repo as get_vector_repo,
)
from ..llm import LLM
from ..llm.mock_llm import MockLLM
from ..embedding import Embedder
from ..config import PipelineConfig
from .extract import extract
from .classify import classify, ClassifyResult
from .review import is_suspicious
from .commit import commit_solution
from .taxonomy_provider import SqlModelTaxonomyProvider


def _make_mock_llm() -> LLM:
    inst = MockLLM()
    inst.effective_backend = "mock_fallback"
    return inst


@dataclass
class RunResult:
    problem_id: int
    confirmed: list[int] = field(default_factory=list)        # SolutionInstance ids
    suspicions: list[int] = field(default_factory=list)       # 进审核队列的 ids
    candidates_new: list[int] = field(default_factory=list)   # 新增 candidate method ids
    # 实际跑通时使用的 LLM 后端 + 错误(若有)
    llm_backend_used: str = "unknown"
    llm_error: str = ""


def run_pipeline(
    problem: Problem,
    *,
    session: Session,
    llm: LLM,
    embedder: Embedder,
    config: PipelineConfig,
    fail_open: bool = True,
) -> RunResult:
    """端到端管线。

    fail_open=True(默认):若 LLM/Embedder 调真实 API 失败,降级为 mock 并在
    result.llm_error 中记录错误信息(不抛异常,确保 UI 还能继续工作)。
    """
    p_repo = ProblemRepo(session)
    m_repo = MethodRepo(session)
    s_repo = SolutionRepo(session)
    v_repo = get_vector_repo()

    provider = SqlModelTaxonomyProvider(session)

    result = RunResult(problem_id=problem.id)
    result.llm_backend_used = getattr(llm, "effective_backend", "unknown")

    # LLM 调用保护:若 http 后端实际失败,降级 mock 重跑一次
    if fail_open and result.llm_backend_used.startswith("http"):
        try:
            # 试探一次
            llm.extract_solution(
                stem_latex=problem.stem_latex,
                reference_solution=problem.reference_solution,
                taxonomy_hint=provider.list_names(str(problem.subject_area.value)),
                subject_area=str(problem.subject_area.value),
            )
        except Exception as e:
            result.llm_error = f"{type(e).__name__}: {e}"
            warnings.warn(
                f"LLM http 调失败,降级为 mock: {e}", stacklevel=2,
            )
            llm = _make_mock_llm()
            llm.effective_backend = "mock_fallback"
            result.llm_backend_used = "mock_fallback"

    def add_si(si):
        s_repo.add(si)
        return s_repo.get(si.id) or si

    drafts = extract(problem, llm=llm, taxonomy_provider=provider,
                     solution_add=add_si)

    if len(drafts) > config.max_methods_per_problem:
        # 全部转可疑(超阈)
        for d in drafts:
            d.review_status = ReviewStatus.DRAFT
            s_repo.update(d)
            result.suspicions.append(d.id)
        return result

    classify_results: list[ClassifyResult] = []
    for d in drafts:
        cr = classify(problem, d, method_repo=m_repo,
                      embedder=embedder, vector_repo=v_repo,
                      config=config)
        classify_results.append(cr)
        if cr.is_new_method and cr.suggested_method_id is not None:
            result.candidates_new.append(cr.suggested_method_id)

    for cr in classify_results:
        si = cr.si
        susp = is_suspicious(
            cr.action,
            confidence=si.confidence,
            methods_count_for_problem=len(drafts),
            config=config,
        )
        if susp:
            si.review_status = ReviewStatus.DRAFT
            s_repo.update(si)
            result.suspicions.append(si.id)
        else:
            si.review_status = ReviewStatus.CONFIRMED
            s_repo.update(si)
            # candidate method 升级为 confirmed
            m = m_repo.get(si.method_id)
            if m is not None and m.status == MethodStatus.CANDIDATE:
                m.status = MethodStatus.CONFIRMED
                m_repo.update(m)
            commit_solution(si, embedder=embedder, vector_repo=v_repo,
                            method_repo=m_repo, solution_repo=s_repo)
            result.confirmed.append(si.id)

    return result