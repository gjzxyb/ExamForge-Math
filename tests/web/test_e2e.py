"""Web 端到端:从空库 → 录入 → 审核 → 浏览方法库 → 报告 → QA。"""

import pytest
from fastapi.testclient import TestClient

from examforge.web import create_app
from examforge.repositories import (
    reset_db_engine_for_tests, reset_vector_for_tests,
)
from examforge.taxonomy import load_seed_methods


@pytest.fixture
def app_client(tmp_path):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    app = create_app(tmp_path / "data")
    # 上传种子
    from examforge.repositories import get_session
    s = get_session()
    load_seed_methods(s)
    yield TestClient(app)
    reset_db_engine_for_tests()
    reset_vector_for_tests()


def test_e2e_pages_all_render(app_client):
    paths = ["/", "/ingest", "/methods", "/review", "/report", "/qa", "/healthz"]
    for p in paths:
        r = app_client.get(p)
        assert r.status_code == 200, f"{p} returned {r.status_code}"


def test_e2e_ingest_runs_pipeline(app_client):
    r = app_client.post("/ingest", data={
        "year": 2023, "region": "全国甲卷", "subject_area": "导数",
        "stem": "若 a>0, 任意实数 x, f(x)=x^3-3x >= -a 恒成立, 求 a 的最大值",
        "reference": "a=2", "source": "e2e test",
    })
    assert r.status_code == 200
    assert "已处理" in r.text


def test_e2e_qa_returns_answer(app_client):
    r = app_client.post("/qa", data={
        "question": "含参不等式恒成立问题怎么做?",
    })
    assert r.status_code == 200
    # 至少应展示回答区
    assert "回答" in r.text or "answer" in r.text.lower()


def test_e2e_methods_list_renders(app_client):
    r = app_client.get("/methods?area=导数")
    assert r.status_code == 200
    assert "分离参数法" in r.text