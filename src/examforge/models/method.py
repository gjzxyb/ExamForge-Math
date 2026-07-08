"""Method:解题方法节点(taxonomy 骨架)。"""

from datetime import datetime
from sqlmodel import Field, SQLModel
from typing import Optional
from .enums import SubjectArea, MethodStatus


class Method(SQLModel, table=True):
    __tablename__ = "methods"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    subject_area: SubjectArea = Field(index=True)
    parent_id: Optional[int] = Field(default=None, foreign_key="methods.id")
    applicability: str = ""       # 适用特征描述
    core_idea: str = ""
    procedure_steps: str = ""    # 通用步骤
    pitfalls: str = ""
    status: MethodStatus = Field(default=MethodStatus.SEED)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
