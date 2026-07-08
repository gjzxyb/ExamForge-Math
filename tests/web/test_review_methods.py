"""审核队列 + 改归并 method 选择端点。"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from examforge.web import create_app
from examforge.repositories import (
    reset_db_engine_for_tests, reset_vector_for_tests,
    problem_repo, method_repo, solution_repo,
    init_db, init_vector_store, get_session, make_fingerprint,
)
from examforge.taxonomy import load_seed_methods
from examforge.models import (
    Problem, Method, SolutionInstance, SubjectArea,
    MethodStatus, ReviewStatus,
)


@pytest.fixture
def client(tmp_path):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    import examforge.config.settings as mod
    mod._store = None
    app = create_app(tmp_path / "data")
    init_db(tmp_path / "data")
    init_vector_store(tmp_path / "data" / "chroma")
    load_seed_methods(get_session())
    yield TestClient(app)
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    mod._store = None


def test_methods_json_returns_all_methods_with_id_name_status_area(client):
    r = client.get("/review/methods.json")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 4  # 至少 4 个导数 seed
    sample = rows[0]
    for k in ("id", "name", "status", "subject_area"):
        assert k in sample
    # 应该有分离参数法
    names = {m["name"] for m in rows}
    assert "分离参数法" in names


def test_methods_json_includes_candidate_after_run(tmp_path):
    """跑一次 ingest 让 LLM 造一个 candidate,然后 JSON 端点应该看到。"""
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    import examforge.config.settings as mod
    mod._store = None
    app = create_app(tmp_path / "data")
    init_db(tmp_path / "data")
    init_vector_store(tmp_path / "data" / "chroma")
    load_seed_methods(get_session())
    c = TestClient(app)
    r = c.get("/review/methods.json")
    before = len(r.json())
    # 不用真调 LLM,直接手工 add 一个 candidate
    m = method_repo().add(Method(
        name="测试候选方法", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.CANDIDATE,
    ))
    r2 = c.get("/review/methods.json")
    after = r2.json()
    assert len(after) == before + 1
    assert any(x["name"] == "测试候选方法" and x["status"] == "candidate" for x in after)
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    mod._store = None


def test_revise_endpoint_accepts_method_id_from_form(client):
    """完整路径:创建 SI → 提交 /revise 带 method_id → 状态变 confirmed 且 method 切换。"""
    p = problem_repo().upsert_by_fingerprint(Problem(
        year=2023, region="A", subject_area=SubjectArea.DERIVATIVE,
        stem_latex="x", content_fingerprint="d" * 16,
    ))
    m_old = method_repo().add(Method(
        name="OldMethod", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.CANDIDATE,
    ))
    m_new = method_repo().add(Method(
        name="NewMethod", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.SEED,
    ))
    s = solution_repo().add(SolutionInstance(
        problem_id=p.id, method_id=m_old.id, key_steps="x",
        review_status=ReviewStatus.DRAFT,
    ))
    r = client.post(f"/review/{s.id}/revise", data={"method_id": m_new.id})
    assert r.status_code in (303, 200)  # 303 redirect; TestClient 默认 follow
    si = solution_repo().get(s.id)
    assert si.method_id == m_new.id
    assert si.review_status == ReviewStatus.CONFIRMED