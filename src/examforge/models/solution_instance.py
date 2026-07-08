"""SolutionInstance:题与方法的连接边(解法实例)。"""

from datetime import datetime
from sqlmodel import Field, SQLModel
from typing import Optional
from .enums import ReviewStatus


class SolutionInstance(SQLModel, table=True):
    __tablename__ = "solution_instances"

    id: Optional[int] = Field(default=None, primary_key=True)
    problem_id: int = Field(foreign_key="problems.id", index=True)
    method_id: int = Field(foreign_key="methods.id", index=True)
    key_steps: str                          # 这道题里的具体演绎
    transfer_note: str = ""                  # 可迁移套路
    embedding_id: Optional[str] = None      # VectorRepo 中的 ID
    confidence: float = 1.0                  # 综合置信度
    review_status: ReviewStatus = Field(default=ReviewStatus.DRAFT, index=True)
    reviewer_note: str = ""
    llm_raw: str = ""                       # LLM 原始 JSON
    created_at: datetime = Field(default_factory=datetime.utcnow)
