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

def test_e2e_ingest_structured_fields_and_figure(app_client):
    from examforge.repositories import problem_repo, make_fingerprint

    stem = "几何题:如图,设椭圆 $C$ 与直线 $l$ 交于 $A,B$, 求弦长。"
    r = app_client.post(
        "/ingest",
        data={
            "year": 2025,
            "region": "结构化测试卷",
            "subject_area": "圆锥曲线",
            "stem": stem,
            "answer": "42",
            "official_analysis_steps": "联立方程,使用韦达定理。",
            "sub_knowledge": "圆锥曲线-直线联立",
            "problem_type_tags": "几何图形,压轴题",
            "ocr_provider": "tencent_math_ocr",
            "source": "structured e2e",
        },
        files={"figure": ("figure.png", b"fake-png-bytes", "image/png")},
    )
    assert r.status_code == 200
    assert "已保存题图" in r.text
    fp = make_fingerprint(stem, 2025, "结构化测试卷")
    p = problem_repo().find_by_fingerprint(fp)
    assert p is not None
    assert p.answer == "42"
    assert p.official_analysis_steps == "联立方程,使用韦达定理。"
    assert p.sub_knowledge == "圆锥曲线-直线联立"
    assert p.problem_type_tags == "几何图形,压轴题"
    assert p.image_ref and p.image_ref.startswith("/uploads/problem-")


def test_report_dropdown_lists_seed_methods(app_client):
    from examforge.repositories import get_session
    from examforge.models import Method, SubjectArea
    from sqlmodel import select

    r = app_client.get("/report")
    assert r.status_code == 200
    assert 'select name="method_id"' in r.text
    assert "分离参数法" in r.text
    assert "seed" in r.text

    s = get_session()
    method = s.exec(
        select(Method).where(
            Method.name == "分离参数法",
            Method.subject_area == SubjectArea.DERIVATIVE,
        )
    ).first()
    assert method is not None
    detail = app_client.get(f"/report?method_id={method.id}")
    assert detail.status_code == 200
    assert "分离参数法 解法专题报告" in detail.text



def test_qa_can_select_method_and_method_example(app_client):
    from examforge.repositories import get_session
    from examforge.models import Method, Problem, SolutionInstance, SubjectArea, ReviewStatus
    from sqlmodel import select

    s = get_session()
    method = s.exec(
        select(Method).where(
            Method.name == "分离参数法",
            Method.subject_area == SubjectArea.DERIVATIVE,
        )
    ).first()
    assert method is not None
    problem = Problem(
        year=2026,
        region="QA选择测试卷",
        subject_area=SubjectArea.DERIVATIVE,
        stem_latex="已知 $f(x)=x^2-a x$，求恒成立时参数范围。",
        answer="a\\in[-2,2]",
        official_analysis_steps="分离参数后研究函数最值。",
        sub_knowledge="导数-恒成立",
        problem_type_tags="方法例题",
        content_fingerprint="qa-select-000001",
    )
    s.add(problem)
    s.commit()
    s.refresh(problem)
    si = SolutionInstance(
        problem_id=problem.id,
        method_id=method.id,
        key_steps="把参数项移到一边，转化为函数最值问题。",
        transfer_note="先判断能否分离参数，再求最值并回代验证。",
        review_status=ReviewStatus.CONFIRMED,
    )
    s.add(si)
    s.commit()

    page = app_client.get("/qa")
    assert page.status_code == 200
    assert 'select name="method_id"' in page.text
    assert 'select name="problem_id"' in page.text
    assert "分离参数法" in page.text
    assert f'value="{problem.id}"' in page.text
    assert "QA选择测试卷" in page.text

    asked = app_client.post("/qa", data={
        "question": "请用所选方法讲解这道例题。",
        "method_id": str(method.id),
        "problem_id": str(problem.id),
    })
    assert asked.status_code == 200
    assert "回答" in asked.text
    assert "引用方法" in asked.text
    assert "分离参数法" in asked.text
    assert f'/problems/{problem.id}' in asked.text
