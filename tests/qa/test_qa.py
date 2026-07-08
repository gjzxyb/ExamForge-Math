import pytest
from examforge.models import (
    Problem, Method, SolutionInstance, SubjectArea,
    MethodStatus, ReviewStatus,
)
from examforge.repositories import (
    init_db, problem_repo, method_repo, solution_repo,
    init_vector_store, vector_repo,
    reset_db_engine_for_tests, reset_vector_for_tests, make_fingerprint,
)
from examforge.embedding import MockEmbedder
from examforge.llm import MockLLM
from examforge.config import PipelineConfig
from examforge.qa import answer
from examforge.pipeline import commit_solution


@pytest.fixture
def ctx(tmp_data_dir):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    init_db(tmp_data_dir)
    init_vector_store(tmp_data_dir / "chroma")
    p = problem_repo().upsert_by_fingerprint(Problem(
        year=2023, region="A", subject_area=SubjectArea.DERIVATIVE,
        stem_latex="x", content_fingerprint="r" * 16,
    ))
    m = method_repo().add(Method(
        name="分离参数法", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.CONFIRMED,
        applicability="参数不等式恒成立,可分离", core_idea="化求最值",
        procedure_steps="分离", pitfalls="等号",
    ))
    s = solution_repo().add(SolutionInstance(
        problem_id=p.id, method_id=m.id, key_steps="构造 g(a)...",
        transfer_note="分离参数套路", review_status=ReviewStatus.CONFIRMED,
    ))
    commit_solution(
        s, embedder=MockEmbedder(), vector_repo=vector_repo(),
        method_repo=method_repo(), solution_repo=solution_repo(),
    )
    yield
    reset_db_engine_for_tests()
    reset_vector_for_tests()


def test_answer_returns_qa_result_with_cited_methods(ctx):
    from examforge.repositories import get_session
    s = get_session()
    r = answer(
        "含参不等式恒成立问题怎么做?",
        session=s, llm=MockLLM(), embedder=MockEmbedder(),
        config=PipelineConfig(),
    )
    assert r.answer  # 至少返回了字符串
    assert isinstance(r.cited_method_names, list)
    assert isinstance(r.cited_problem_ids, list)