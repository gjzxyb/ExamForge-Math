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


def _draft_solution(method_id: int, *, stem: str = "x", key_steps: str = "步骤1：构造辅助函数"):
    p = problem_repo().upsert_by_fingerprint(Problem(
        year=2024, region="B", subject_area=SubjectArea.DERIVATIVE,
        stem_latex=stem, content_fingerprint=make_fingerprint(stem, 2024, "B"),
    ))
    return solution_repo().add(SolutionInstance(
        problem_id=p.id, method_id=method_id, key_steps=key_steps,
        transfer_note="可迁移到同类导数题", review_status=ReviewStatus.DRAFT,
    ))


def test_confirm_endpoint_promotes_method_and_commits_to_method_library(client):
    m = method_repo().add(Method(
        name="审核确认入库法", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.CANDIDATE,
    ))
    s = _draft_solution(m.id, stem="confirm endpoint")

    r = client.post(f"/review/{s.id}/confirm")
    assert r.status_code in (303, 200)

    si = solution_repo().get(s.id)
    assert si.review_status == ReviewStatus.CONFIRMED
    assert si.embedding_id
    assert method_repo().get(m.id).status == MethodStatus.CONFIRMED

    methods_page = client.get("/methods?status=confirmed")
    assert methods_page.status_code == 200
    assert "审核确认入库法" in methods_page.text
    detail = client.get(f"/methods/{m.id}")
    assert detail.status_code == 200
    assert "实现该方法的条件" in detail.text
    assert "通用解题步骤" in detail.text
    assert "审题识别" in detail.text
    assert "关键转化" in detail.text
    assert "暂无通用步骤" not in detail.text
    assert "方法变式：举一反三" in detail.text
    assert f'/problems/{s.problem_id}' in detail.text
    assert "可迁移到同类导数题" in detail.text

    problem_page = client.get(f"/problems/{s.problem_id}")
    assert problem_page.status_code == 200
    assert "已确认解法实例" in problem_page.text
    assert "审核确认入库法" in problem_page.text


def test_revise_endpoint_promotes_candidate_target_and_commits(client):
    m_old = method_repo().add(Method(
        name="待改归并旧方法", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.CANDIDATE,
    ))
    m_new = method_repo().add(Method(
        name="改归并后入库法", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.CANDIDATE,
    ))
    s = _draft_solution(m_old.id, stem="revise endpoint")

    r = client.post(f"/review/{s.id}/revise", data={"method_id": m_new.id})
    assert r.status_code in (303, 200)

    si = solution_repo().get(s.id)
    assert si.method_id == m_new.id
    assert si.review_status == ReviewStatus.CONFIRMED
    assert si.embedding_id
    assert method_repo().get(m_new.id).status == MethodStatus.CONFIRMED
    assert "改归并后入库法" in client.get("/methods?status=confirmed").text


def test_approve_new_endpoint_creates_confirmed_method_and_commits(client):
    m_old = method_repo().add(Method(
        name="待批准旧候选", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.CANDIDATE,
    ))
    s = _draft_solution(m_old.id, stem="approve new endpoint")

    r = client.post(f"/review/{s.id}/approve_new", data={
        "name": "管理员批准新方法",
        "subject_area": SubjectArea.DERIVATIVE.value,
        "applicability": "适用于含参单调性题",
        "core_idea": "先分离参数再讨论最值",
        "key_theorem": "拉格朗日中值定理：把函数差转化为某点导数",
        "secondary_theorems": "罗尔定理\n导数零点与单调性分段结论",
        "procedure_steps": "1. 分离参数\n2. 求导判定",
        "pitfalls": "注意端点",
    })
    assert r.status_code in (303, 200)

    method = method_repo().find_by_name("管理员批准新方法", SubjectArea.DERIVATIVE)
    assert method is not None
    assert method.status == MethodStatus.CONFIRMED
    assert method.key_theorem.startswith("拉格朗日中值定理")
    assert "罗尔定理" in method.secondary_theorems
    detail = client.get(f"/methods/{method.id}")
    assert detail.status_code == 200
    assert "关键定理与二级定理" in detail.text
    assert "拉格朗日中值定理" in detail.text
    assert "罗尔定理" in detail.text
    assert "导数零点与单调性分段结论" in detail.text
    si = solution_repo().get(s.id)
    assert si.method_id == method.id
    assert si.review_status == ReviewStatus.CONFIRMED
    assert si.embedding_id
    assert "管理员批准新方法" in client.get("/methods?status=confirmed").text


def test_method_detail_extracts_theorem_from_confirmed_example_llm_raw(client):
    m = method_repo().add(Method(
        name="例题定理抽取法", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.CONFIRMED,
    ))
    p = problem_repo().upsert_by_fingerprint(Problem(
        year=2025, region="C", subject_area=SubjectArea.DERIVATIVE,
        stem_latex="证明存在零点", content_fingerprint=make_fingerprint("theorem raw", 2025, "C"),
    ))
    solution_repo().add(SolutionInstance(
        problem_id=p.id, method_id=m.id, key_steps="用定理完成关键转化",
        transfer_note="可迁移到零点存在性题",
        review_status=ReviewStatus.CONFIRMED,
        llm_raw='{"key_theorem":"零点存在定理：连续函数两端异号则区间内存在零点","secondary_theorems":["介值定理","闭区间连续函数最值定理"]}',
    ))

    detail = client.get(f"/methods/{m.id}")
    assert detail.status_code == 200
    assert "零点存在定理" in detail.text
    assert "介值定理" in detail.text
    assert "闭区间连续函数最值定理" in detail.text
    assert f'/problems/{p.id}' in detail.text



def test_methods_page_allows_manual_add_and_shows_author_thinking(client):
    page = client.get("/methods")
    assert page.status_code == 200
    assert "手动添加方法" in page.text
    assert "出题人思维分析" in page.text

    r = client.post("/methods", data={
        "name": "手动维护设参转化法",
        "subject_area": SubjectArea.DERIVATIVE.value,
        "status": MethodStatus.CONFIRMED.value,
        "applicability": "含参恒成立；参数可与主变量分离",
        "core_idea": "把命题转化为参数与函数最值的比较",
        "key_theorem": "闭区间连续函数最值定理",
        "secondary_theorems": "导数与单调性关系",
        "procedure_steps": "1. 分离参数\n2. 求导找最值\n3. 回代验证",
        "author_thinking_analysis": "命题人通过端点和等号条件设陷；考查学生能否先识别参数位置。",
        "pitfalls": "忘记端点；忽略等号成立",
    }, follow_redirects=False)
    assert r.status_code == 303

    method = method_repo().find_by_name("手动维护设参转化法", SubjectArea.DERIVATIVE)
    assert method is not None
    assert method.status == MethodStatus.CONFIRMED
    assert "命题人通过端点" in method.author_thinking_analysis

    detail = client.get(f"/methods/{method.id}")
    assert detail.status_code == 200
    assert "出题人思维分析" in detail.text
    assert "人工维护分析" in detail.text
    assert "命题人通过端点" in detail.text
    assert "命题意图" in detail.text
    assert "设陷方式" in detail.text
    assert "破题观察" in detail.text


def test_method_detail_has_variant_generator_error_graph_trend_styles_and_confidence(client):
    m = method_repo().add(Method(
        name="分离参数自测法", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.CONFIRMED,
        applicability="含参恒成立；可分离参数",
        core_idea="转化为函数最值",
        key_theorem="闭区间连续函数最值定理",
        procedure_steps="1. 分离参数\n2. 求导求最值",
        pitfalls="忘记端点",
    ))
    for year in (2018, 2021, 2025):
        p = problem_repo().upsert_by_fingerprint(Problem(
            year=year, region=f"R{year}", subject_area=SubjectArea.DERIVATIVE,
            stem_latex=f"含参恒成立 {year}",
            sub_knowledge="导数-恒成立-分离参数",
            problem_type_tags="参数范围",
            content_fingerprint=make_fingerprint(f"trend-{year}", year, f"R{year}"),
        ))
        solution_repo().add(SolutionInstance(
            problem_id=p.id, method_id=m.id,
            key_steps="分离参数后求最值", transfer_note="参数范围自测",
            confidence=0.8, review_status=ReviewStatus.CONFIRMED,
            llm_raw='{"common_errors":["分离参数时忽略分母符号"]}',
        ))
    bad_p = problem_repo().upsert_by_fingerprint(Problem(
        year=2026, region="BAD", subject_area=SubjectArea.DERIVATIVE,
        stem_latex="不适合分离参数", content_fingerprint=make_fingerprint("bad", 2026, "BAD"),
    ))
    solution_repo().add(SolutionInstance(
        problem_id=bad_p.id, method_id=m.id, key_steps="误套分离参数",
        review_status=ReviewStatus.REJECTED, reviewer_note="条件不满足，属于误套方法",
    ))

    detail = client.get(f"/methods/{m.id}?generate_variants=1&variant_count=3")
    assert detail.status_code == 200
    for text in (
        "变式生成器", "反向生成自测题", "自测变式 A",
        "错因图谱", "负例知识库", "分离参数时忽略分母符号", "条件不满足",
        "跨年对比", "2018", "2025",
        "讲解风格适配", "直觉理解版", "严谨证明版", "口诀记忆版",
        "置信度标注", "覆盖历史题", "反例/拒绝样本",
        "出题人思维分析",
    ):
        assert text in detail.text



def test_methods_page_can_discover_web_methods_and_add_candidate(client):
    page = client.get("/methods")
    assert page.status_code == 200
    assert "全网搜索发现方法" in page.text

    discover = client.get("/methods/discover", params={
        "query": "高中数学 导数 压轴题 隐零点法",
        "area": SubjectArea.DERIVATIVE.value,
        "max_results": "3",
    })
    assert discover.status_code == 200
    assert "候选方法" in discover.text
    assert "加入方法库候选" in discover.text
    assert "隐零点法" in discover.text or "同构构造函数法" in discover.text

    r = client.post("/methods/discover/add", data={
        "name": "全网发现隐零点法",
        "subject_area": SubjectArea.DERIVATIVE.value,
        "applicability": "适用于导数零点和极值点无法显式求出的压轴题",
        "core_idea": "从全网搜索发现，先设隐零点再代换消元。",
        "procedure_steps": "1. 设隐零点\n2. 消元\n3. 回代验证",
        "pitfalls": "需人工复核来源",
        "source_url": "https://example.com/implicit-zero-method",
        "status": MethodStatus.CANDIDATE.value,
    }, follow_redirects=False)
    assert r.status_code == 303
    method = method_repo().find_by_name("全网发现隐零点法", SubjectArea.DERIVATIVE)
    assert method is not None
    assert method.status == MethodStatus.CANDIDATE
    assert "全网搜索来源" in method.core_idea
