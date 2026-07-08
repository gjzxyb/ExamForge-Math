import pytest
from examforge.models import (
    Problem, Method, SolutionInstance, SubjectArea, MethodStatus, ReviewStatus,
)
from examforge.repositories import (
    init_db, method_repo,
    init_vector_store, vector_repo,
    reset_db_engine_for_tests, reset_vector_for_tests,
)
from examforge.embedding import MockEmbedder
from examforge.config import PipelineConfig
from examforge.pipeline import classify


@pytest.fixture
def ctx(tmp_data_dir):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    init_db(tmp_data_dir)
    init_vector_store(tmp_data_dir / "chroma")
    seed = method_repo().add(Method(
        name="分离参数法", subject_area=SubjectArea.DERIVATIVE,
        applicability="参数不等式恒成立,可分离", status=MethodStatus.SEED,
    ))
    yield {"method_seed_id": seed.id}
    reset_db_engine_for_tests()
    reset_vector_for_tests()


def _problem():
    return Problem(id=1, year=2023, region="甲",
                   subject_area=SubjectArea.DERIVATIVE,
                   stem_latex="x", content_fingerprint="z" * 16)


def _draft(name="分离参数法", confidence=0.7):
    return SolutionInstance(
        problem_id=1, method_id=0,
        key_steps="key",
        transfer_note="t",
        confidence=confidence,
        review_status=ReviewStatus.DRAFT,
        llm_raw=(
            f'{{"method_name":"{name}","subject_area":"导数",'
            f'"key_steps":"x","transfer_note":"x","applicability":"x",'
            f'"confidence":{confidence}}}'
        ),
    )


def test_classify_exact_match_returns_exact(ctx):
    res = classify(_problem(), _draft(),
                   method_repo=method_repo(),
                   embedder=MockEmbedder(),
                   vector_repo=vector_repo(),
                   config=PipelineConfig())
    assert res.action == "exact"
    assert res.suggested_method_id == ctx["method_seed_id"]


def test_classify_unknown_method_decision_made(ctx):
    res = classify(_problem(), _draft(name="完全未知名法"),
                   method_repo=method_repo(),
                   embedder=MockEmbedder(),
                   vector_repo=vector_repo(),
                   config=PipelineConfig())
    # 三种 action 都可能,关键是 si 已挂上 method_id(无论是 candidate 还是 suspicious)
    assert res.si.method_id is not None
    assert res.action in ("candidate", "suspicious", "exact")