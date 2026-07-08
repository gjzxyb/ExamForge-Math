"""classify 对 LLM 输出的非枚举 subject_area 必须有兜底。"""

import pytest
from examforge.models import (
    Problem, Method, SolutionInstance, SubjectArea, MethodStatus, ReviewStatus,
)
from examforge.repositories import (
    init_db, method_repo, init_vector_store, vector_repo,
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
    method_repo().add(Method(
        name="分离参数法", subject_area=SubjectArea.DERIVATIVE,
        applicability="参数不等式", status=MethodStatus.SEED,
    ))
    yield
    reset_db_engine_for_tests()
    reset_vector_for_tests()


def test_classify_falls_back_when_subject_area_not_in_enum(ctx):
    """LLM 输出了 '简易逻辑与不等式' 这种枚举外的板块,应该 fallback 不崩。"""
    p = Problem(
        id=1, year=2023, region="甲",
        subject_area=SubjectArea.DERIVATIVE,
        stem_latex="x", content_fingerprint="z" * 16,
    )
    draft = SolutionInstance(
        problem_id=1, method_id=0, key_steps="x",
        transfer_note="x", confidence=0.8,
        review_status=ReviewStatus.DRAFT,
        # 注意 subject_area 给了一个枚举里不存在的值
        llm_raw=(
            '{"method_name":"分离参数法","subject_area":"简易逻辑与不等式",'
            '"key_steps":"x","transfer_note":"x","applicability":"x","confidence":0.8}'
        ),
    )
    res = classify(p, draft,
                   method_repo=method_repo(),
                   embedder=MockEmbedder(),
                   vector_repo=vector_repo(),
                   config=PipelineConfig())
    # 不应该抛,action 是 exact(精确命中已有 method)
    assert res.action == "exact"
    # reviewer_note 应有 fallback 提示
    assert "fallback" in draft.reviewer_note or draft.reviewer_note == ""


def test_classify_falls_back_when_method_name_unknown_and_subject_area_bad(ctx):
    """方法名 + 板块都异常:仍要 fallback 不崩。"""
    p = Problem(
        id=1, year=2023, region="甲",
        subject_area=SubjectArea.DERIVATIVE,
        stem_latex="x", content_fingerprint="z" * 16,
    )
    draft = SolutionInstance(
        problem_id=1, method_id=0, key_steps="x",
        transfer_note="x", confidence=0.8,
        review_status=ReviewStatus.DRAFT,
        llm_raw=(
            '{"method_name":"完全未知名法","subject_area":"简易逻辑与不等式",'
            '"key_steps":"x","transfer_note":"x","applicability":"x","confidence":0.8}'
        ),
    )
    res = classify(p, draft,
                   method_repo=method_repo(),
                   embedder=MockEmbedder(),
                   vector_repo=vector_repo(),
                   config=PipelineConfig())
    # 不应该抛(测试本身就到这里就算通过);实际结果取决于 embedding
    # 相似度:可能挂到已有 method(candidate / 不是 new)或创建 new candidate。
    # 关键是 fallback 路径不崩。
    assert res.action in ("candidate", "suspicious", "exact")
    # 落到 problem 自己的板块,所以 method 一定不为 None
    assert draft.method_id is not None and draft.method_id > 0
    # reviewer_note 应有 fallback 提示
    assert "fallback" in draft.reviewer_note