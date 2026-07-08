import pytest
from examforge.models import (
    Problem, Method, SolutionInstance, SubjectArea,
    MethodStatus, ReviewStatus,
)
from examforge.repositories import (
    init_db, problem_repo, method_repo, solution_repo,
    init_vector_store, vector_repo,
    reset_db_engine_for_tests, reset_vector_for_tests, make_fingerprint,
)
from examforge.embedding import MockEmbedder
from examforge.pipeline import commit_solution


@pytest.fixture
def ctx(tmp_data_dir):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    init_db(tmp_data_dir)
    init_vector_store(tmp_data_dir / "chroma")
    p = problem_repo().upsert_by_fingerprint(Problem(
        year=2023, region="A", subject_area=SubjectArea.DERIVATIVE,
        stem_latex="x", content_fingerprint="k" * 16,
    ))
    m = method_repo().add(Method(
        name="X", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.CONFIRMED,
    ))
    s = solution_repo().add(SolutionInstance(
        problem_id=p.id, method_id=m.id, key_steps="构造...",
        transfer_note="...", review_status=ReviewStatus.CONFIRMED,
    ))
    yield {"si_id": s.id}
    reset_db_engine_for_tests()
    reset_vector_for_tests()


def test_commit_writes_embedding_for_confirmed(ctx):
    si = solution_repo().get(ctx["si_id"])
    vec_id = commit_solution(
        si,
        embedder=MockEmbedder(),
        vector_repo=vector_repo(),
        method_repo=method_repo(),
        solution_repo=solution_repo(),
    )
    assert vec_id
    assert si.embedding_id == vec_id


def test_commit_skips_draft(tmp_data_dir):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    init_db(tmp_data_dir)
    init_vector_store(tmp_data_dir / "chroma")
    p = problem_repo().upsert_by_fingerprint(Problem(
        year=2023, region="A", subject_area=SubjectArea.DERIVATIVE,
        stem_latex="x", content_fingerprint="m" * 16,
    ))
    m = method_repo().add(Method(
        name="Y", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.CONFIRMED,
    ))
    s = solution_repo().add(SolutionInstance(
        problem_id=p.id, method_id=m.id, key_steps="x",
        review_status=ReviewStatus.DRAFT,
    ))
    out = commit_solution(
        s, embedder=MockEmbedder(), vector_repo=vector_repo(),
        method_repo=method_repo(), solution_repo=solution_repo(),
    )
    assert out == ""
    reset_db_engine_for_tests()
    reset_vector_for_tests()