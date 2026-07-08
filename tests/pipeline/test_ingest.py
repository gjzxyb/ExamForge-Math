import pytest
from examforge.repositories import (
    init_db, problem_repo, reset_db_engine_for_tests,
)
from examforge.models import SubjectArea
from examforge.pipeline import ingest_problem, IngestValidationError


@pytest.fixture
def repo(tmp_data_dir):
    reset_db_engine_for_tests()
    init_db(tmp_data_dir)
    yield problem_repo()
    reset_db_engine_for_tests()


def test_ingest_creates_new(repo):
    p = ingest_problem(
        stem_latex="设 $f(x)=x^3$",
        year=2023, region="全国甲卷",
        subject_area=SubjectArea.DERIVATIVE,
        reference_solution="略",
        source="试卷",
        repo=repo,
    )
    assert p.id is not None
    assert p.subject_area == SubjectArea.DERIVATIVE


def test_ingest_is_idempotent_by_fingerprint(repo):
    a = ingest_problem(stem_latex=" $x^3$ ", year=2023, region="全国甲卷",
                       subject_area=SubjectArea.DERIVATIVE, repo=repo)
    b = ingest_problem(stem_latex="$x^3$", year=2023, region="全国甲卷",
                       subject_area=SubjectArea.DERIVATIVE, repo=repo)
    assert a.id == b.id


def test_ingest_rejects_empty(repo):
    with pytest.raises(IngestValidationError):
        ingest_problem(stem_latex="   ", year=2023, region="甲",
                       subject_area=SubjectArea.DERIVATIVE, repo=repo)


def test_ingest_rejects_html(repo):
    with pytest.raises(IngestValidationError):
        ingest_problem(stem_latex="<script>alert(1)</script>", year=2023,
                       region="甲", subject_area=SubjectArea.DERIVATIVE, repo=repo)


def test_ingest_accepts_string_subject_area(repo):
    p = ingest_problem(stem_latex="略", year=2023, region="甲",
                       subject_area="导数", repo=repo)
    assert p.subject_area == SubjectArea.DERIVATIVE