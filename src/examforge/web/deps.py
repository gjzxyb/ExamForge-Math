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
    """复用项目会话，并在请求前失效缓存以读取后台任务的最新提交。"""
    s = get_session()
    s.expire_all()
    try:
        yield s
    finally:
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
