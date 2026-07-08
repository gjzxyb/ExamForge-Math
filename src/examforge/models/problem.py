"""Problem:一道压轴题。"""

from datetime import datetime
from sqlmodel import Field, SQLModel
from typing import Optional
from .enums import SubjectArea


class Problem(SQLModel, table=True):
    __tablename__ = "problems"

    id: Optional[int] = Field(default=None, primary_key=True)
    year: int = Field(index=True)
    region: str = Field(index=True)  # 如 "全国甲卷"
    subject_area: SubjectArea = Field(index=True)
    stem_latex: str
    reference_solution: Optional[str] = None
    source: str = ""
    content_fingerprint: str = Field(index=True, unique=True)  # SHA-256 前 16 hex
    image_ref: Optional[str] = None  # 图像入口预留,第一版为 None
    created_at: datetime = Field(default_factory=datetime.utcnow)
