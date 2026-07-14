"""Pipeline 步骤 1:Ingest(录入 + 幂等去重)。"""

from ..models import Problem, SubjectArea
from ..repositories import make_fingerprint, ProblemRepo
from .errors import IngestValidationError


def _validate(stem_latex: str) -> None:
    if not stem_latex or not stem_latex.strip():
        raise IngestValidationError("stem_latex 不能为空")
    # LaTeX 基本合法性:不允许裸 HTML
    if "<script" in stem_latex.lower():
        raise IngestValidationError("stem_latex 包含非法 HTML")


def ingest_problem(
    *,
    stem_latex: str,
    year: int,
    region: str,
    subject_area: SubjectArea | str,
    reference_solution: str | None = None,
    answer: str | None = None,
    official_analysis_steps: str | None = None,
    sub_knowledge: str = "",
    problem_type_tags: str = "",
    image_ref: str | None = None,
    source: str = "",
    repo: ProblemRepo,
) -> Problem:
    """录入一道题,按指纹幂等去重。

    返回已存在的或新建的 Problem。
    """
    _validate(stem_latex)
    if isinstance(subject_area, str):
        subject_area = SubjectArea(subject_area)
    fp = make_fingerprint(stem_latex, year, region)
    p = Problem(
        year=year,
        region=region,
        subject_area=subject_area,
        stem_latex=stem_latex.strip(),
        reference_solution=reference_solution,
        answer=answer,
        official_analysis_steps=official_analysis_steps,
        sub_knowledge=sub_knowledge.strip(),
        problem_type_tags=problem_type_tags.strip(),
        image_ref=image_ref,
        source=source,
        content_fingerprint=fp,
    )
    return repo.upsert_by_fingerprint(p)