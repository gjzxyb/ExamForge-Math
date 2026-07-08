import pytest
from sqlalchemy import select

from examforge.models import (
    Problem, Method, SubjectArea, ReviewStatus,
)
from examforge.repositories import (
    init_db, problem_repo,
    init_vector_store, vector_repo,
    reset_db_engine_for_tests, reset_vector_for_tests,
    make_fingerprint,
)
from examforge.embedding import MockEmbedder
from examforge.llm import MockLLM
from examforge.config import PipelineConfig
from examforge.pipeline import run_pipeline
from examforge.taxonomy import load_seed_methods


@pytest.fixture
def ctx(tmp_data_dir):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    init_db(tmp_data_dir)
    init_vector_store(tmp_data_dir / "chroma")
    # 加载种子
    from examforge.repositories import get_session
    s = get_session()
    # 清空(防止测试间残留)
    for m in s.exec(select(Method)):
        s.delete(m)
    s.commit()
    load_seed_methods(s)
    yield tmp_data_dir
    reset_db_engine_for_tests()
    reset_vector_for_tests()


def test_pipeline_run_clean_problem_gets_confirmed(ctx):
    cfg = PipelineConfig()
    # mock LLM 启发式:_looks_like_parametric -> "分离参数法"(若在 hint 中)
    p = Problem(
        year=2023, region="全国甲卷",
        subject_area=SubjectArea.DERIVATIVE,
        stem_latex="若 a>0, 任意实数 x, 都有 f(x)=x^3-3x >= -a 恒成立, 求 a 的最大值。",
        reference_solution="a=2",
        content_fingerprint=make_fingerprint("fx-x^3-3x-param", 2023, "全国甲卷"),
    )
    p_repo = problem_repo()
    p = p_repo.upsert_by_fingerprint(p)

    from examforge.repositories import get_session
    s = get_session()
    r = run_pipeline(p, session=s, llm=MockLLM(),
                     embedder=MockEmbedder(), config=cfg)
    # 至少一种行为已发生
    assert len(r.confirmed) + len(r.suspicions) >= 1
    # clean 题应进入 confirmed(命中 seed "分离参数法" + 高于 auto_confirm 阈值)
    assert len(r.confirmed) >= 1