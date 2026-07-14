"""LLM 结构化输出 schema。"""

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator


def normalize_llm_text(value: Any) -> str:
    """兼容真实 LLM 把字符串字段误返回成 list/dict/None 的情况。

    JSON schema 已要求字符串,但部分模型会把 key_steps、summary 等字段
    返回为步骤数组。这里统一转为可读文本,避免可恢复格式偏差导致整条
    ingest 管线降级 mock。
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            text = normalize_llm_text(item)
            if text:
                parts.append(text)
        return "\n".join(parts)
    if isinstance(value, dict):
        # 常见形态: {"step":"..."} 或 {"name":"...","desc":"..."};
        # 保留键名有助于后续人工排查模型输出。
        try:
            return json.dumps(value, ensure_ascii=False)
        except TypeError:
            return str(value).strip()
    return str(value).strip()


class ProposedMethodUse(BaseModel):
    """LLM 提出的某方法使用情况。"""

    @field_validator(
        "method_name", "subject_area", "key_steps", "transfer_note",
        "applicability", "key_theorem", mode="before",
    )
    @classmethod
    def normalize_text_fields(cls, value: Any) -> str:
        return normalize_llm_text(value)

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

    @field_validator("summary", mode="before")
    @classmethod
    def normalize_summary(cls, value: Any) -> str:
        return normalize_llm_text(value)

    summary: str = Field(description="整道题的一句话思路综述")
    methods: list[ProposedMethodUse]
    overall_confidence: float = Field(ge=0.0, le=1.0)


class GeneratedAnswer(BaseModel):
    """缺失答案时由 LLM/API 生成的结构化答案。"""

    @field_validator("answer", "analysis_steps", mode="before")
    @classmethod
    def normalize_text_fields(cls, value: Any) -> str:
        return normalize_llm_text(value)

    @field_validator("answer")
    @classmethod
    def answer_must_not_be_blank(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("生成答案不能为空")
        return cleaned

    answer: str = Field(description="题目的答案/最终结果,可含 LaTeX")
    analysis_steps: str = Field(default="", description="生成答案所依据的简要解题步骤")
    confidence: float = Field(ge=0.0, le=1.0, default=0.7, description="生成答案置信度")


class ReportedSections(BaseModel):
    """Reporter 的输出(章节化结构)。"""

    @field_validator(
        "intro", "core_idea", "procedure", "applicability",
        "pitfalls", "examples_markdown", mode="before",
    )
    @classmethod
    def normalize_text_fields(cls, value: Any) -> str:
        return normalize_llm_text(value)

    intro: str
    core_idea: str
    procedure: str
    applicability: str
    pitfalls: str
    examples_markdown: str  # Markdown 表格


class QAResult(BaseModel):
    """QA 的输出。"""

    @field_validator("answer", mode="before")
    @classmethod
    def normalize_answer(cls, value: Any) -> str:
        return normalize_llm_text(value)

    answer: str
    cited_method_names: list[str]
    cited_problem_ids: list[int]