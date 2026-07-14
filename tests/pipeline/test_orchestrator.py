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


def test_pipeline_http_llm_timeout_falls_back_to_mock(ctx):
    from examforge.repositories import get_session
    from examforge.llm.http_llm import LLMHttpError

    class TimeoutLLM:
        effective_backend = "http"

        def extract_solution(self, **kwargs):
            raise LLMHttpError("无法连接 LLM: The read operation timed out")

    p = problem_repo().upsert_by_fingerprint(Problem(
        year=2026,
        region="超时测试卷",
        subject_area=SubjectArea.DERIVATIVE,
        stem_latex="若 a>0, 任意实数 x, f(x)=x^3-3x >= -a 恒成立, 求 a 的最大值。",
        reference_solution="a=2",
        content_fingerprint=make_fingerprint("timeout-fallback", 2026, "超时测试卷"),
    ))
    r = run_pipeline(
        p,
        session=get_session(),
        llm=TimeoutLLM(),
        embedder=MockEmbedder(),
        config=PipelineConfig(),
    )
    assert r.llm_backend_used == "mock_fallback"
    assert "timed out" in r.llm_error
    assert "增大 LLM Timeout" in r.llm_error
    assert len(r.confirmed) + len(r.suspicions) >= 1



def test_pipeline_http_llm_probe_retries_three_times_until_success(ctx):
    from examforge.repositories import get_session
    from examforge.llm.http_llm import LLMHttpError
    from examforge.llm.schemas import ExtractedSolution, ProposedMethodUse

    class FlakyProbeLLM:
        effective_backend = "http"

        def __init__(self):
            self.calls = 0

        def extract_solution(self, **kwargs):
            self.calls += 1
            if self.calls < 3:
                raise LLMHttpError(f"probe failed {self.calls}")
            return ExtractedSolution(
                summary="思路",
                methods=[ProposedMethodUse(
                    method_name="分离参数法",
                    subject_area="导数",
                    key_steps="分离参数后求函数最值",
                    transfer_note="恒成立转最值",
                    applicability="含参恒成立",
                    confidence=0.9,
                )],
                overall_confidence=0.9,
            )

    llm = FlakyProbeLLM()
    p = problem_repo().upsert_by_fingerprint(Problem(
        year=2026,
        region="试探重试卷",
        subject_area=SubjectArea.DERIVATIVE,
        stem_latex="若 a>0, 任意实数 x, f(x)=x^3-3x >= -a 恒成立, 求 a 的最大值。",
        reference_solution="a=2",
        content_fingerprint=make_fingerprint("probe-retry", 2026, "试探重试卷"),
    ))
    r = run_pipeline(
        p,
        session=get_session(),
        llm=llm,
        embedder=MockEmbedder(),
        config=PipelineConfig(),
    )
    assert llm.calls == 4  # 前两次试探失败,第 3 次试探成功,第 4 次正式 Extract
    assert r.llm_backend_used == "http"
    assert r.llm_error == ""
    assert len(r.confirmed) + len(r.suspicions) >= 1


def test_pipeline_force_review_keeps_clean_problem_in_review_queue(ctx):
    from examforge.repositories import get_session, solution_repo

    p = problem_repo().upsert_by_fingerprint(Problem(
        year=2026,
        region="强制审核测试卷",
        subject_area=SubjectArea.DERIVATIVE,
        stem_latex="若 a>0, 任意实数 x, f(x)=x^3-3x >= -a 恒成立, 求 a 的最大值。",
        reference_solution="a=2",
        content_fingerprint=make_fingerprint("force-review", 2026, "强制审核测试卷"),
    ))
    r = run_pipeline(
        p,
        session=get_session(),
        llm=MockLLM(),
        embedder=MockEmbedder(),
        config=PipelineConfig(),
        force_review=True,
    )
    assert r.confirmed == []
    assert len(r.suspicions) >= 1
    queued = solution_repo().list_by_review_status(ReviewStatus.DRAFT)
    assert any(si.id in r.suspicions for si in queued)
    assert any("新录入题目默认进入审核队列" in si.reviewer_note for si in queued)
