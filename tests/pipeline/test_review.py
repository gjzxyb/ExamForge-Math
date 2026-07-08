import pytest
from examforge.models import (
    Problem, Method, SolutionInstance, SubjectArea,
    MethodStatus, ReviewStatus,
)
from examforge.repositories import (
    init_db, problem_repo, method_repo, solution_repo,
    reset_db_engine_for_tests, make_fingerprint,
)
from examforge.config import PipelineConfig
from examforge.pipeline import (
    is_suspicious, confirm, reject, revise_method, NotInReviewQueue,
)


@pytest.fixture
def ctx(tmp_data_dir):
    reset_db_engine_for_tests()
    init_db(tmp_data_dir)
    p = problem_repo().upsert_by_fingerprint(Problem(
        year=2023, region="A", subject_area=SubjectArea.DERIVATIVE,
        stem_latex="x", content_fingerprint="a" * 16,
    ))
    m = method_repo().add(Method(
        name="X", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.CANDIDATE,
    ))
    s = solution_repo().add(SolutionInstance(
        problem_id=p.id, method_id=m.id, key_steps="k",
        review_status=ReviewStatus.DRAFT,
    ))
    yield {"problem_id": p.id, "method_id": m.id, "si_id": s.id}
    reset_db_engine_for_tests()


def test_is_suspicious_by_action_suspicious():
    assert is_suspicious("suspicious", confidence=0.9,
                         methods_count_for_problem=1,
                         config=PipelineConfig())


def test_is_suspicious_by_low_confidence():
    cfg = PipelineConfig()
    assert is_suspicious("exact", confidence=0.3,
                         methods_count_for_problem=1, config=cfg)


def test_is_suspicious_by_too_many_methods():
    cfg = PipelineConfig()
    assert not is_suspicious("exact", confidence=0.9,
                             methods_count_for_problem=3, config=cfg)
    assert is_suspicious("exact", confidence=0.9,
                         methods_count_for_problem=4, config=cfg)


def test_confirm_promotes_candidate_method(ctx):
    m_repo = method_repo()
    s_repo = solution_repo()
    si = confirm(ctx["si_id"], note="ok", solution_repo=s_repo,
                 method_repo=m_repo)
    assert si.review_status == ReviewStatus.CONFIRMED
    m = m_repo.get(ctx["method_id"])
    assert m.status == MethodStatus.CONFIRMED


def test_reject_sets_status(ctx):
    s = reject(ctx["si_id"], note="no", solution_repo=solution_repo())
    assert s.review_status == ReviewStatus.REJECTED


def test_revise_method_changes_method_and_confirms(ctx):
    new_m = method_repo().add(Method(
        name="Y", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.SEED,
    ))
    si = revise_method(ctx["si_id"], new_m.id, solution_repo=solution_repo())
    assert si.method_id == new_m.id
    assert si.review_status == ReviewStatus.CONFIRMED


def test_confirm_unknown_raises(ctx):
    with pytest.raises(NotInReviewQueue):
        confirm(9999, note="x", solution_repo=solution_repo())