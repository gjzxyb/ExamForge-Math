from sqlalchemy.engine import Engine
from sqlmodel import Session
from .engine import get_engine
from .problem_repo import ProblemRepo
from .method_repo import MethodRepo
from .solution_repo import SolutionRepo


def problem_repo_factory(s: Session | None = None) -> ProblemRepo:
    return ProblemRepo(s or session_factory())


def method_repo_factory(s: Session | None = None) -> MethodRepo:
    return MethodRepo(s or session_factory())


def solution_repo_factory(s: Session | None = None) -> SolutionRepo:
    return SolutionRepo(s or session_factory())


def session_factory() -> Session:
    return Session(get_engine())