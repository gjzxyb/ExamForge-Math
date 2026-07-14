"""LLM 结构化输出 schema。"""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ProposedMethodUse(BaseModel):
    """LLM 提出的某方法使用情况。"""

    @field_validator("secondary_theorems", mode="before")
    @classmethod
    def normalize_secondary_theorems(cls, value: Any) -> list[str]:
        """兼容真实 LLM 把空数组误写成空字符串/逗号分隔字符串的情况。"""
        if value is None or value == "":
            return []
        if isinstance(value, str):
            parts: list[str] = []
            for line in value.replace("\r", "\n").split("\n"):
                for part in line.replace("；", ";").replace("，", ",").split(";"):
                    for sub in part.split(","):
                        item = sub.strip()
                        if item:
                            parts.append(item)
            return parts
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if str(value).strip() else []

    method_name: str = Field(description="方法名,优先使用既有 taxonomy 中的名称")
    subject_area: str = Field(description="板块,如 '导数'")
    key_steps: str = Field(description="此方法在本题的关键步骤")
    transfer_note: str = Field(description="可迁移套路")
    applicability: str = Field(description="此方法的适用特征描述")
    key_theorem: str = Field(default="", description="本题若有更优定理/关键定理,写定理名称与简述;没有则留空")
    secondary_theorems: list[str] = Field(default_factory=list, description="本题用到的二级定理、推论或常用结论;没有则空列表")
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