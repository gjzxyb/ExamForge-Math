"""Web 层共享依赖与 bootstrap。"""

from pathlib import Path
from sqlmodel import Session
from fastapi import Depends, Request

from ..config import get_config
from ..llm import get_llm
from ..embedding import get_embedder
from ..repositories import (
    init_db, init_vector_store,
    problem_repo_factory, method_repo_factory, solution_repo_factory,
    get_session,
)


def ensure_init(app_data_dir: Path) -> None:
    init_db(app_data_dir)
    init_vector_store(app_data_dir / "chroma")


def get_session_dep():
    """FastAPI 依赖:每次请求返回全局复用 session(在同一 session 内事务一致)。"""
    s = get_session()
    try:
        yield s
    finally:
        # 共享 session,不 close;FastAPI 多请求会复用
        pass


def problem_repo_dep(s: Session = Depends(get_session_dep)):
    return problem_repo_factory(s)


def method_repo_dep(s: Session = Depends(get_session_dep)):
    return method_repo_factory(s)


def solution_repo_dep(s: Session = Depends(get_session_dep)):
    return solution_repo_factory(s)


def llm_dep():
    return get_llm()


def embedder_dep():
    return get_embedder()


def config_dep():
    return get_config()