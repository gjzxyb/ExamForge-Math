from examforge.models import SolutionInstance, ReviewStatus


def test_solution_instance_default_is_draft():
    s = SolutionInstance(
        problem_id=1, method_id=1,
        key_steps="构造 g(a)=...",
    )
    assert s.review_status == ReviewStatus.DRAFT
    assert s.confidence == 1.0
    assert s.embedding_id is None
