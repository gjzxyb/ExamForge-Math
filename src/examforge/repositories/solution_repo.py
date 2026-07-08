"""SolutionInstance 仓库。"""

from sqlmodel import Session, select
from typing import Optional
from ..models import SolutionInstance, ReviewStatus
from .engine import get_session


class SolutionRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, si: SolutionInstance) -> SolutionInstance:
        self.session.add(si)
        self.session.commit()
        self.session.refresh(si)
        return si

    def get(self, si_id: int) -> Optional[SolutionInstance]:
        return self.session.get(SolutionInstance, si_id)

    def list_by_review_status(self, status: ReviewStatus) -> list[SolutionInstance]:
        return list(
            self.session.exec(
                select(SolutionInstance).where(SolutionInstance.review_status == status)
            )
        )

    def list_confirmed_by_method(self, method_id: int) -> list[SolutionInstance]:
        return list(
            self.session.exec(
                select(SolutionInstance).where(
                    SolutionInstance.method_id == method_id,
                    SolutionInstance.review_status == ReviewStatus.CONFIRMED,
                )
            )
        )

    def update(self, si: SolutionInstance) -> SolutionInstance:
        self.session.add(si)
        self.session.commit()
        self.session.refresh(si)
        return si


def solution_repo() -> SolutionRepo:
    return SolutionRepo(get_session())