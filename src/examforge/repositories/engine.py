"""存储引擎初始化(SQLite + Chroma)。"""

from pathlib import Path
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import text
from sqlalchemy.engine import Engine
from typing import Optional
from ..models import Problem, Method, SolutionInstance


_engine: Optional[Engine] = None
_session: Optional[Session] = None


def _ensure_problem_columns(engine: Engine) -> None:
    """为已有 SQLite 数据库补齐新增录入字段。

    SQLModel.metadata.create_all 只会建新表,不会修改旧表;本项目已有 data/examforge.db,
    因此启动时做轻量、幂等的 ALTER TABLE 迁移。
    """
    required = {
        "answer": "VARCHAR",
        "official_analysis_steps": "VARCHAR",
        "sub_knowledge": "VARCHAR DEFAULT ''",
        "problem_type_tags": "VARCHAR DEFAULT ''",
    }
    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(problems)"))}
        for name, ddl_type in required.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE problems ADD COLUMN {name} {ddl_type}"))


def _ensure_method_columns(engine: Engine) -> None:
    """为已有 SQLite 方法表补齐定理字段。"""
    required = {
        "key_theorem": "VARCHAR DEFAULT ''",
        "secondary_theorems": "VARCHAR DEFAULT ''",
        "author_thinking_analysis": "VARCHAR DEFAULT ''",
    }
    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(methods)"))}
        for name, ddl_type in required.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE methods ADD COLUMN {name} {ddl_type}"))


def init_db(data_dir: Path, db_filename: str = "examforge.db") -> Engine:
    """初始化 SQLite 引擎 + 创建表,并打开一个复用的 session。多次调用返回同一引擎。"""
    global _engine, _session
    if _engine is not None:
        return _engine
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / db_filename
    url = f"sqlite:///{db_path}"
    _engine = create_engine(url, echo=False, future=True)
    SQLModel.metadata.create_all(_engine)
    _ensure_problem_columns(_engine)
    _ensure_method_columns(_engine)
    _session = Session(_engine)
    return _engine


def reset_db_engine_for_tests() -> None:
    """测试辅助:重置全局引擎与 session 以便换目录。"""
    global _engine, _session
    if _session is not None:
        try:
            _session.close()
        except Exception:
            pass
    _engine = None
    _session = None


def get_engine() -> Engine:
    """若未初始化,自动以 ./data 为目录初始化一次。"""
    if _engine is None:
        init_db(Path("data"))
    return _engine


def get_session() -> Session:
    """拿全局复用的 Session。同进程内同一对象始终在同一 session 上,
    避免 SQLAlchemy 'Object already attached' 错误。
    """
    if _engine is None or _session is None:
        raise RuntimeError("init_db() 必须先调用")
    return _session


def session_factory() -> Session:
    """工厂:返回全局复用 session。
    仓库/测试代码应当优先使用本函数而不是直接访问 _session。
    """
    return get_session()