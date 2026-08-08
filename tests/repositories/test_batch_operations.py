"""测试批量操作性能优化。"""

import pytest
from examforge.repositories import init_db, method_repo, problem_repo, reset_db_engine_for_tests
from examforge.models import Method, Problem, SubjectArea, MethodStatus


@pytest.fixture
def db(tmp_data_dir):
    reset_db_engine_for_tests()
    init_db(tmp_data_dir)
    yield
    reset_db_engine_for_tests()


def test_method_repo_get_many(db):
    """测试批量获取方法。"""
    repo = method_repo()
    m1 = Method(name="M1", subject_area=SubjectArea.DERIVATIVE, applicability="A1", status=MethodStatus.SEED)
    m2 = Method(name="M2", subject_area=SubjectArea.DERIVATIVE, applicability="A2", status=MethodStatus.SEED)
    repo.add(m1)
    repo.add(m2)

    methods = repo.get_many([m1.id, m2.id])
    assert len(methods) == 2
    assert {m.name for m in methods} == {"M1", "M2"}


def test_method_repo_get_many_empty(db):
    """测试批量获取空列表。"""
    repo = method_repo()
    methods = repo.get_many([])
    assert methods == []


def test_method_repo_add_many(db):
    """测试批量添加方法。"""
    repo = method_repo()
    methods = [
        Method(name=f"M{i}", subject_area=SubjectArea.DERIVATIVE, applicability=f"A{i}", status=MethodStatus.SEED)
        for i in range(5)
    ]

    added = repo.add_many(methods)
    assert len(added) == 5
    assert all(m.id is not None for m in added)


def test_method_repo_update_many(db):
    """测试批量更新方法。"""
    repo = method_repo()
    methods = [
        Method(name=f"M{i}", subject_area=SubjectArea.DERIVATIVE, applicability=f"A{i}", status=MethodStatus.SEED)
        for i in range(3)
    ]
    added = repo.add_many(methods)

    for m in added:
        m.status = MethodStatus.CONFIRMED

    updated = repo.update_many(added)
    assert all(m.status == MethodStatus.CONFIRMED for m in updated)


def test_problem_repo_get_many(db):
    """测试批量获取题目。"""
    from examforge.repositories.problem_repo import make_fingerprint
    repo = problem_repo()

    p1 = Problem(
        year=2023, region="甲", subject_area=SubjectArea.DERIVATIVE,
        stem_latex="题1", content_fingerprint=make_fingerprint("题1", 2023, "甲")
    )
    p2 = Problem(
        year=2024, region="乙", subject_area=SubjectArea.CONIC,
        stem_latex="题2", content_fingerprint=make_fingerprint("题2", 2024, "乙")
    )
    repo.upsert_by_fingerprint(p1)
    repo.upsert_by_fingerprint(p2)

    problems = repo.get_many([p1.id, p2.id])
    assert len(problems) == 2
    assert {p.stem_latex for p in problems} == {"题1", "题2"}


def test_problem_repo_list_by_area_with_pagination(db):
    """测试分页列表。"""
    from examforge.repositories.problem_repo import make_fingerprint
    repo = problem_repo()

    for i in range(10):
        p = Problem(
            year=2023, region=f"区{i}", subject_area=SubjectArea.DERIVATIVE,
            stem_latex=f"题{i}", content_fingerprint=make_fingerprint(f"题{i}", 2023, f"区{i}")
        )
        repo.upsert_by_fingerprint(p)

    page1 = repo.list_by_area(SubjectArea.DERIVATIVE, limit=5, offset=0)
    page2 = repo.list_by_area(SubjectArea.DERIVATIVE, limit=5, offset=5)

    assert len(page1) == 5
    assert len(page2) == 5
    assert set(p.id for p in page1).isdisjoint(set(p.id for p in page2))
