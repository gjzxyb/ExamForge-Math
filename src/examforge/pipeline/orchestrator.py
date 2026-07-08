"""端到端管线编排。"""

from dataclasses import dataclass, field
from sqlmodel import Session
from ..models import (
    Problem, ReviewStatus, MethodStatus,
)
from ..repositories import (
    ProblemRepo, MethodRepo, SolutionRepo, vector_repo as get_vector_repo,
)
from ..llm import LLM
from ..embedding import Embedder
from ..config import PipelineConfig
from .extract import extract
from .classify import classify, ClassifyResult
from .review import is_suspicious
from .commit import commit_solution
from .taxonomy_provider import SqlModelTaxonomyProvider


@dataclass
class RunResult:
    problem_id: int
    confirmed: list[int] = field(default_factory=list)        # SolutionInstance ids
    suspicions: list[int] = field(default_factory=list)       # 进审核队列的 ids
    candidates_new: list[int] = field(default_factory=list)   # 新增 candidate method ids


def run_pipeline(
    problem: Problem,
    *,
    session: Session,
    llm: LLM,
    embedder: Embedder,
    config: PipelineConfig,
) -> RunResult:
    p_repo = ProblemRepo(session)
    m_repo = MethodRepo(session)
    s_repo = SolutionRepo(session)
    v_repo = get_vector_repo()

    provider = SqlModelTaxonomyProvider(session)

    result = RunResult(problem_id=problem.id)

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