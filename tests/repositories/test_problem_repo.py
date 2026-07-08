"""Problem 仓库测试,使用临时数据目录。"""

import pytest
from examforge.repositories import (
    init_db, problem_repo, reset_db_engine_for_tests, make_fingerprint,
)
from examforge.models import Problem, SubjectArea


@pytest.fixture
def db(tmp_data_dir):
    reset_db_engine_for_tests()
    init_db(tmp_data_dir)
    yield
    reset_db_engine_for_tests()


def test_upsert_inserts_new(db):
    repo = problem_repo()
    p = Problem(
        year=2023, region="全国甲卷",
        subject_area=SubjectArea.DERIVATIVE,
        stem_latex="$f(x)=x^3-3x$",
        content_fingerprint=make_fingerprint("$f(x)=x^3-3x$", 2023, "全国甲卷"),
    )
    out = repo.upsert_by_fingerprint(p)
    assert out.id is not None


def test_upsert_dedup_by_fingerprint(db):
    repo = problem_repo()
    fp = "deadbeef" + "0" * 8
    p1 = Problem(
        year=2023, region="全国甲卷",
        subject_area=SubjectArea.DERIVATIVE,
        stem_latex="A", content_fingerprint=fp,
    )
    p2 = Problem(
        year=2024, region="全国乙卷",
        subject_area=SubjectArea.CONIC,
        stem_latex="B", content_fingerprint=fp,
    )
    a = repo.upsert_by_fingerprint(p1)
    b = repo.upsert_by_fingerprint(p2)
    assert a.id == b.id  # 同指纹应该合一


def test_list_by_area(db):
    repo = problem_repo()
    fp_a = "a" * 16
    fp_b = "b" * 16
    repo.upsert_by_fingerprint(Problem(
        year=2023, region="A", subject_area=SubjectArea.DERIVATIVE,
        stem_latex="d1", content_fingerprint=fp_a,
    ))
    repo.upsert_by_fingerprint(Problem(
        year=2023, region="A", subject_area=SubjectArea.CONIC,
        stem_latex="c1", content_fingerprint=fp_b,
    ))
    assert len(repo.list_by_area(SubjectArea.DERIVATIVE)) == 1
    assert len(repo.list_by_area(SubjectArea.CONIC)) == 1


def test_make_fingerprint_stable():
    fp1 = make_fingerprint("stem", 2023, "甲卷")
    fp2 = make_fingerprint("  stem  ", 2023, "甲卷")
    assert fp1 == fp2
    assert len(fp1) == 16