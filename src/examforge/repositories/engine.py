"""存储引擎初始化(SQLite + Chroma)。"""

from pathlib import Path
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.engine import Engine
from typing import Optional
from ..models import Problem, Method, SolutionInstance


_engine: Optional[Engine] = None


def init_db(data_dir: Path, db_filename: str = "examforge.db") -> Engine:
    """初始化 SQLite 引擎 + 创建表。多次调用返回同一引擎。"""
    global _engine
    if _engine is not None:
        return _engine
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / db_filename
    url = f"sqlite:///{db_path}"
    _engine = create_engine(url, echo=False, future=True)
    SQLModel.metadata.create_all(_engine)
    return _engine


def reset_db_engine_for_tests() -> None:
    """测试辅助:重置全局引擎以便换目录。"""
    global _engine
    _engine = None


def get_engine() -> Engine:
    """若未初始化,自动以 ./data 为目录初始化一次。
    用于测试代码里要拿到 Engine 构造 Session 时使用。
    """
    if _engine is None:
        init_db(Path("data"))
    return _engine


def get_session() -> Session:
    """拿一个新 Session。"""
    if _engine is None:
        raise RuntimeError("init_db() 必须先调用")
    return Session(_engine)


def session_factory() -> Session:
    """工厂:返回一个新 Session,自动确保 engine 已初始化。
    仓库/测试代码应当优先使用本函数而不是直接访问 _engine。
    """
    return Session(get_engine())