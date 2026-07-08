import pytest
from examforge.repositories import (
    init_db, problem_repo, method_repo, solution_repo,
    reset_db_engine_for_tests, make_fingerprint,
)
from examforge.models import (
    Problem, Method, SolutionInstance, SubjectArea,
    MethodStatus, ReviewStatus,
)


@pytest.fixture
def db(tmp_data_dir):
    reset_db_engine_for_tests()
    init_db(tmp_data_dir)
    p = problem_repo().upsert_by_fingerprint(Problem(
        year=2023, region="A", subject_area=SubjectArea.DERIVATIVE,
        stem_latex="x", content_fingerprint=make_fingerprint("x", 2023, "A"),
    ))
    m = method_repo().add(Method(
        name="X", subject_area=SubjectArea.DERIVATIVE, status=MethodStatus.SEED,
    ))
    yield (p.id, m.id)
    reset_db_engine_for_tests()


def test_solution_state_lifecycle(db):
    pid, mid = db
    sr = solution_repo()
    s = sr.add(SolutionInstance(
        problem_id=pid, method_id=mid, key_steps="...",
        review_status=ReviewStatus.DRAFT,
    ))
    assert s.review_status == ReviewStatus.DRAFT
    draft_list = sr.list_by_review_status(ReviewStatus.DRAFT)
    assert any(x.id == s.id for x in draft_list)

    s.review_status = ReviewStatus.CONFIRMED
    sr.update(s)
    confirmed_for_method = sr.list_confirmed_by_method(mid)
    assert any(x.id == s.id for x in confirmed_for_method)