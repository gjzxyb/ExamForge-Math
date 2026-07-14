from datetime import datetime
from examforge.models import Problem, SubjectArea


def test_problem_defaults_and_roundtrip():
    p = Problem(
        year=2023, region="全国甲卷",
        subject_area=SubjectArea.DERIVATIVE,
        stem_latex="设函数 f(x)=x^3-3x...",
        content_fingerprint="abc123",
    )
    assert p.id is None
    assert p.created_at is not None
    assert p.reference_solution is None
    assert p.answer is None
    assert p.official_analysis_steps is None
    assert p.sub_knowledge == ""
    assert p.problem_type_tags == ""
    assert isinstance(p.created_at, datetime)
