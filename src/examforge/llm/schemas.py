"""LLM 结构化输出 schema。"""

from pydantic import BaseModel, Field


class ProposedMethodUse(BaseModel):
    """LLM 提出的某方法使用情况。"""
    method_name: str = Field(description="方法名,优先使用既有 taxonomy 中的名称")
    subject_area: str = Field(description="板块,如 '导数'")
    key_steps: str = Field(description="此方法在本题的关键步骤")
    transfer_note: str = Field(description="可迁移套路")
    applicability: str = Field(description="此方法的适用特征描述")
    confidence: float = Field(ge=0.0, le=1.0, description="LLM 自报置信度")


class ExtractedSolution(BaseModel):
    """Extract 步骤的结构化输出。"""
    summary: str = Field(description="整道题的一句话思路综述")
    methods: list[ProposedMethodUse]
    overall_confidence: float = Field(ge=0.0, le=1.0)


class ReportedSections(BaseModel):
    """Reporter 的输出(章节化结构)。"""
    intro: str
    core_idea: str
    procedure: str
    applicability: str
    pitfalls: str
    examples_markdown: str  # Markdown 表格


class QAResult(BaseModel):
    """QA 的输出。"""
    answer: str
    cited_method_names: list[str]
    cited_problem_ids: list[int]