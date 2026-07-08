"""Pipeline 步骤 2:Extract(LLM 提炼 → draft SolutionInstance)。

注意:不实际归到 Method 实体,留待 Classify(此处只输出 raw + confidence)。
"""

from typing import Protocol
from ..models import Problem, SolutionInstance, ReviewStatus
from ..llm import LLM


class TaxonomyProvider(Protocol):
    """提供给定板块的候选方法名清单。"""
    def list_names(self, subject_area: str) -> list[str]: ...


def extract(
    problem: Problem,
    *,
    llm: LLM,
    taxonomy_provider: TaxonomyProvider,
    solution_add,  # Signature: (si: SolutionInstance) -> SolutionInstance
) -> list[SolutionInstance]:
    hint = taxonomy_provider.list_names(str(problem.subject_area.value))
    out = llm.extract_solution(
        stem_latex=problem.stem_latex,
        reference_solution=problem.reference_solution,
        taxonomy_hint=hint,
        subject_area=str(problem.subject_area.value),
    )
    created: list[SolutionInstance] = []
    for m in out.methods:
        si = SolutionInstance(
            problem_id=problem.id,
            method_id=0,            # 待 Classify 阶段确认/写入
            key_steps=m.key_steps,
            transfer_note=m.transfer_note,
            confidence=(m.confidence + out.overall_confidence) / 2.0,
            review_status=ReviewStatus.DRAFT,
            llm_raw=m.model_dump_json(),
        )
        created.append(solution_add(si))
    return created