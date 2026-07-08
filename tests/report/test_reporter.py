import pytest
from examforge.models import (
    Problem, Method, SolutionInstance, SubjectArea,
    MethodStatus, ReviewStatus,
)
from examforge.repositories import (
    init_db, problem_repo, method_repo, solution_repo,
    reset_db_engine_for_tests, make_fingerprint,
)
from examforge.llm import MockLLM
from examforge.report import generate_report


@pytest.fixture
def ctx(tmp_data_dir):
    reset_db_engine_for_tests()
    init_db(tmp_data_dir)
    p = problem_repo().upsert_by_fingerprint(Problem(
        year=2023, region="A", subject_area=SubjectArea.DERIVATIVE,
        stem_latex="x", content_fingerprint="q" * 16,
    ))
    m = method_repo().add(Method(
        name="分离参数法", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.CONFIRMED,
        applicability="参数不等式恒成立",
        core_idea="化为 f(a)≥g(x) 后求最值",
        procedure_steps="1. 整理 2. 分离 3. 求最值",
        pitfalls="忘验等号",
    ))
    solution_repo().add(SolutionInstance(
        problem_id=p.id, method_id=m.id, key_steps="x",
        transfer_note="把参数 a 分离到左侧", review_status=ReviewStatus.CONFIRMED,
    ))
    yield m.id
    reset_db_engine_for_tests()


def test_generate_report_returns_markdown_with_header_and_count(ctx):
    from examforge.repositories import get_session
    s = get_session()
    out = generate_report(ctx, session=s, llm=MockLLM())
    assert out.startswith("# 分离参数法 解法专题报告")
    assert "共 1 道" in out
    assert "通用步骤" in out