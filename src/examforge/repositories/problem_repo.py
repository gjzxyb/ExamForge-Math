"""Problem 仓库:幂等 upsert、按指纹查重、列表与按板块筛。"""

import hashlib
from datetime import datetime
from typing import Optional
from sqlmodel import Session, select
from ..models import Problem, SubjectArea
from .engine import get_session


def make_fingerprint(stem: str, year: int, region: str) -> str:
    """从题干+元数据生成指纹(SHA-256 截前 16 hex)。"""
    raw = f"{year}|{region}|{stem.strip()}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


class ProblemRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_fingerprint(self, fp: str) -> Optional[Problem]:
        return self.session.exec(
            select(Problem).where(Problem.content_fingerprint == fp)
        ).first()

    def upsert_by_fingerprint(self, problem: Problem) -> Problem:
        """已存在则更新,否则插入。返回最终对象。"""
        existing = self.find_by_fingerprint(problem.content_fingerprint)
        if existing is None:
            self.session.add(problem)
            self.session.commit()
            self.session.refresh(problem)
            return problem
        # in-place update on existing
        existing.year = problem.year
        existing.region = problem.region
        existing.subject_area = problem.subject_area
        existing.stem_latex = problem.stem_latex
        existing.reference_solution = problem.reference_solution
        existing.source = problem.source
        existing.image_ref = problem.image_ref
        existing.created_at = existing.created_at or datetime.utcnow()
        self.session.add(existing)
        self.session.commit()
        self.session.refresh(existing)
        return existing

    def get(self, problem_id: int) -> Optional[Problem]:
        return self.session.get(Problem, problem_id)

    def list_by_area(self, area: SubjectArea, limit: int = 100) -> list[Problem]:
        return list(
            self.session.exec(
                select(Problem).where(Problem.subject_area == area).limit(limit)
            )
        )


def problem_repo() -> ProblemRepo:
    return ProblemRepo(get_session())