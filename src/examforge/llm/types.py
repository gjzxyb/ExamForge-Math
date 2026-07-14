"""LLM 抽象接口。"""

from typing import Protocol, runtime_checkable
from .schemas import ExtractedSolution, ReportedSections, QAResult, GeneratedAnswer


@runtime_checkable
class LLM(Protocol):
    def extract_solution(self, *, stem_latex, reference_solution,
                         taxonomy_hint, subject_area) -> ExtractedSolution: ...
    def generate_answer(self, *, stem_latex, subject_area, reference_solution=None) -> GeneratedAnswer: ...
    def render_report(self, *, method_name, applicability, core_idea,
                      procedure, pitfalls, examples) -> ReportedSections: ...
    def answer_question(self, *, question, method_doc, examples) -> QAResult: ...