"""CLI 启动时的快速 bootstrap。"""

from pathlib import Path
from sqlmodel import Session
from ..repositories import (
    init_db, init_vector_store,
)


def bootstrap(data_dir: Path) -> None:
    init_db(data_dir)
    init_vector_store(data_dir / "chroma")


def get_session_for_cli(data_dir: Path) -> Session:
    """确保 DB 已初始化并返回复用的全局 session。"""
    init_db(data_dir)
    from ..repositories import get_session
    return get_session()