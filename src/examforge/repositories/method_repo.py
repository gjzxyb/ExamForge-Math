"""Method 仓库 + seed 上传。"""

from sqlmodel import Session, select
from typing import Optional
from ..models import Method, MethodStatus, SubjectArea
from .engine import get_session


class MethodRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, method_id: int) -> Optional[Method]:
        return self.session.get(Method, method_id)

    def get_many(self, method_ids: list[int]) -> list[Method]:
        """批量获取方法(优化:单次查询)。"""
        if not method_ids:
            return []
        stmt = select(Method).where(Method.id.in_(method_ids))
        return list(self.session.exec(stmt))

    def find_by_name(self, name: str, area: SubjectArea) -> Optional[Method]:
        return self.session.exec(
            select(Method).where(Method.name == name, Method.subject_area == area)
        ).first()

    def list_by_area(self, area: SubjectArea, status: Optional[MethodStatus] = None) -> list[Method]:
        stmt = select(Method).where(Method.subject_area == area)
        if status is not None:
            stmt = stmt.where(Method.status == status)
        return list(self.session.exec(stmt))

    def list_confirmed_by_area(self, area: SubjectArea) -> list[Method]:
        return self.list_by_area(area, MethodStatus.CONFIRMED)

    def add(self, method: Method) -> Method:
        self.session.add(method)
        self.session.commit()
        self.session.refresh(method)
        return method

    def add_many(self, methods: list[Method]) -> list[Method]:
        """批量添加方法(优化:批量提交)。"""
        if not methods:
            return []
        for m in methods:
            self.session.add(m)
        self.session.commit()
        for m in methods:
            self.session.refresh(m)
        return methods

    def update(self, method: Method) -> Method:
        self.session.add(method)
        self.session.commit()
        self.session.refresh(method)
        return method

    def update_many(self, methods: list[Method]) -> list[Method]:
        """批量更新方法(优化:批量提交)。"""
        if not methods:
            return []
        for m in methods:
            self.session.add(m)
        self.session.commit()
        for m in methods:
            self.session.refresh(m)
        return methods


def method_repo() -> MethodRepo:
    return MethodRepo(get_session())