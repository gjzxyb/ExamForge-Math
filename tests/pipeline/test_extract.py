from examforge.models import Problem, SubjectArea, SolutionInstance, ReviewStatus
from examforge.pipeline import extract, TaxonomyProvider
from examforge.llm import MockLLM


class FakeTaxonomy(TaxonomyProvider):
    def __init__(self, names):
        self.names = names

    def list_names(self, subject_area: str) -> list[str]:
        return self.names


def test_extract_creates_drafts_in_solution_repo():
    p = Problem(id=1, year=2023, region="甲",
                subject_area=SubjectArea.DERIVATIVE,
                stem_latex="若 a>0, 任意 x, f(x)>=a 恒成立",
                content_fingerprint="x" * 16)
    stored: list[SolutionInstance] = []
    def add(si: SolutionInstance) -> SolutionInstance:
        si.id = len(stored) + 1
        stored.append(si)
        return si

    out = extract(p, llm=MockLLM(),
                  taxonomy_provider=FakeTaxonomy(["分离参数法"]),
                  solution_add=add)
    assert len(out) >= 1
    assert all(s.review_status == ReviewStatus.DRAFT for s in out)
    assert all(s.method_id == 0 for s in out)


def test_extract_propagates_llm_confidence():
    p = Problem(id=2, year=2023, region="甲",
                subject_area=SubjectArea.DERIVATIVE,
                stem_latex="题", content_fingerprint="y" * 16)
    stored: list[SolutionInstance] = []
    def add(si):
        si.id = len(stored) + 1
        stored.append(si)
        return si
    out = extract(p, llm=MockLLM(),
                  taxonomy_provider=FakeTaxonomy([]),
                  solution_add=add)
    assert all(0.0 <= s.confidence <= 1.0 for s in out)