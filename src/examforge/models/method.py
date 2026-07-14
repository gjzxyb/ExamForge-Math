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
    key_theorem: str = ""  # 本方法优先使用的关键定理/更优定理
    secondary_theorems: str = ""  # 二级定理、推论、常用结论；多条可换行
    procedure_steps: str = ""    # 通用步骤
    author_thinking_analysis: str = ""  # 出题人思维分析：命题意图、陷阱布置、能力考查
    pitfalls: str = ""
    status: MethodStatus = Field(default=MethodStatus.SEED)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
