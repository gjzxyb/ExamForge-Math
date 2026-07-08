"""TaxonomyProvider 的 SQLModel 实现(在 Pipeline 内部用,而不是 mock)。"""

from sqlmodel import Session
from sqlalchemy import select
from ..models import Method


class SqlModelTaxonomyProvider:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_names(self, subject_area: str) -> list[str]:
        from ..models import SubjectArea
        stmt = select(Method).where(Method.subject_area == SubjectArea(subject_area))
        # 兼容性:SQLModel 0.0.39 + SQLAlchemy 2.x 下,session.exec 可能返回 Row。
        # 用 scalars() 强制转 ORM 实例,然后取 .name。
        result = self.session.execute(stmt)
        return [m.name for m in result.scalars().all()]