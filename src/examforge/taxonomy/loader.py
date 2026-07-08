"""把 seeds 转成 SQLModel Method 对象,带 area/status 字段。"""

from typing import Iterable
from sqlmodel import Session
from sqlalchemy import select
from ..models import Method, SubjectArea, MethodStatus
from .seed_derivative import ALL_DERIVATIVE
from .seed_conic import ALL_CONIC


ALL_SEEDS = [
    (SubjectArea.DERIVATIVE, ALL_DERIVATIVE),
    (SubjectArea.CONIC, ALL_CONIC),
]


def all_seed_specs() -> Iterable[tuple[SubjectArea, dict]]:
    for area, items in ALL_SEEDS:
        for spec in items:
            yield area, spec


def seed_methods() -> list[Method]:
    return [
        Method(
            name=spec["name"],
            subject_area=area,
            applicability=spec["applicability"],
            core_idea=spec["core_idea"],
            procedure_steps=spec["procedure_steps"],
            pitfalls=spec["pitfalls"],
            status=MethodStatus.SEED,
        )
        for area, spec in all_seed_specs()
    ]


def load_seed_methods(session: Session) -> list[Method]:
    """幂等:同 area+name 已存在则跳过。"""
    out: list[Method] = []
    for m in seed_methods():
        exists = session.exec(
            select(Method).where(
                Method.name == m.name, Method.subject_area == m.subject_area
            )
        ).first()
        if exists is None:
            session.add(m)
            out.append(m)
    session.commit()
    return out