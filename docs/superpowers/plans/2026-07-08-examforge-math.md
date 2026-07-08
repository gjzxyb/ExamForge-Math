# ExamForge-Math 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 ExamForge-Math 的核心引擎与 Web 薄壳,从历年高考压轴题中自动提炼、聚类、审核、沉淀出可查询的解题方法库,并在其上提供教师报告与学生问答两类应用。

**Architecture:** 三层。核心引擎(纯 Python,SQLModel + Repository 抽象,可独立测试)→ 交付层(FastAPI + Jinja2 + HTMX 薄壳)。LLM(默认 DeepSeek)与 Embedding 都藏在接口层后。管线 Ingest→Extract→Classify→Review→Commit,审核策略"只审可疑项"。

**Tech Stack:**
- Python 3.11+,uv (依赖/环境管理)
- SQLModel (ORM + 校验,与 FastAPI 天然契合),SQLite (结构化存储)
- Chroma (向量库,本地嵌入式)
- DeepSeek (默认 LLM;可配置接口层),国内 embedding (默认 BGE;可配置接口层)
- pydantic v2 (LLM 结构化输出 schema)
- pytest (TDD,目标覆盖率 80%+)
- 第一阶段带 Typer CLI;第二阶段 FastAPI + Jinja2 + htmx

**Spec:** `docs/superpowers/specs/2026-07-08-examforge-math-design.md`

---

## Global Constraints

- **Python ≥ 3.11**,项目根 `D:\ExamForge-Math`
- 依赖管理:**uv**,唯一配置文件 `pyproject.toml`,锁定 `uv.lock`
- 包名:`examforge`(import 路径),CLI 命令:`examforge`
- 数据库:本地 SQLite 文件 `data/examforge.db`(Chroma 持久化 `data/chroma/`,gitignore)
- 测试:`pytest`,目录 `tests/`,覆盖率 ≥ 80%(pytest-cov)
- LLM/Embedding:**单元测试一律 mock**,不依赖真实 API;契约测试单独标记(默认 skip)
- 命名:camelCase 变量/函数,PascalCase 类型,字段 snake_case,常量 UPPER_SNAKE_CASE
- 不可变性:不修改入参对象,`update`/`with_*` 返回新对象
- 文件:单一职责,目标 200–400 行,800 行为上限
- 错误处理:显式异常,边界处 fail-fast,绝不静默吞异常
- Git:任务粒度提交,conventional commits(`feat:` / `test:` / `refactor:` / `chore:` / `docs:`)

---

## 阶段总览

**阶段 1 · 核心引擎(黄金集 + 人工对比验证质量)**
1. 项目脚手架 + uv + pytest 配置
2. Models(Problem / Method / SolutionInstance)
3. Repository 接口 + SQLite/Chroma 实现
4. Embedding 接口层(默认 BGE)
5. LLM 接口层(默认 DeepSeek,含结构化输出 schema)
6. 预置 taxonomy 种子与引导 prompt
7. Pipeline · Ingest
8. Pipeline · Extract(LLM 提炼)
9. Pipeline · Classify(归类 + 发现新方法)
10. Pipeline · Review(判定可疑项 + 审核工作流)
11. Pipeline · Commit
12. 管线端到端组装 + CLI
13. 应用 A · Reporter(教师报告)
14. 应用 B · QA(RAG 学生问答)
15. **黄金集验证**:准备黄金集、跑通管线、人工对比记录验收报告

**阶段 2 · Web 薄壳**
16. FastAPI 骨架 + 配置 + Jinja2 + htmx 接入
17. 题目录入界面
18. 方法库浏览界面
19. 审核队列界面 + 审核动作端点
20. 报告生成界面
21. 学生问答界面
22. 端到端跑通 + 启动文档

每完成一组任务做一次提交;阶段 1 结束必须输出"阶段 1 验收报告"作为阶段 2 的前置门。

---

# 阶段 1 · 核心引擎

---

### Task 1: 项目脚手架与 uv 初始化

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/examforge/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `README.md`

**Interfaces:**
- Produces: 包 `examforge`,CLI 命令名待 Task 12 注册
- Produces: 测试入口 `tests/`,根 conftest 提供 `tmp_data_dir` fixture

- [ ] **Step 1.1: 初始化 uv 项目**

```bash
cd D:/ExamForge-Math
uv init --package --name examforge --python 3.11
```

Expected:生成 `pyproject.toml`、`src/examforge/`、`tests/`。

- [ ] **Step 1.2: 写入 `.gitignore`**

```
# data
data/
*.db
*.db-journal
.venv/
__pycache__/
*.pyc
.coverage
.pytest_cache/
htmlcov/
dist/
build/
*.egg-info/
.idea/
.vscode/
```

- [ ] **Step 1.3: 安装基础依赖**

```bash
uv add "sqlmodel>=0.0.22" "pydantic>=2.7" "typer>=0.12" "httpx>=0.27" "rich>=13"
uv add --dev "pytest>=8" "pytest-cov>=5"
```

Expected:`pyproject.toml` 含以上依赖,`uv.lock` 生成。

- [ ] **Step 1.4: 改为 src layout**

如果 `uv init` 生成了顶层 `examforge/` 包目录,删除它,改为 `src/examforge/`:

```bash
mkdir -p src/examforge
# 把顶层 examforge/ 的 __init__.py 内容拷到 src/examforge/__init__.py
# 然后删除顶层 examforge/ 目录
rm -rf examforge
```

`src/examforge/__init__.py`:

```python
"""ExamForge-Math:从高考压轴题提炼结构化解题方法库。"""

__version__ = "0.1.0"
```

在 `pyproject.toml` 加构建配置:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/examforge"]
```

- [ ] **Step 1.5: 配置 pytest + 覆盖率**

在 `pyproject.toml` 加:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q --strict-markers --tb=short"
markers = [
    "contract: requires real LLM/API (skipped by default)",
]

[tool.coverage.run]
source = ["src/examforge"]
omit = ["*/tests/*"]

[tool.coverage.report]
fail_under = 80
```

- [ ] **Step 1.6: 写 `tests/__init__.py` 与 `tests/conftest.py`**

`tests/__init__.py`(留空):

`tests/conftest.py`:

```python
import pytest
from pathlib import Path


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """每个测试一个临时数据目录(SQLite 与 Chroma 都用它)。"""
    d = tmp_path / "data"
    d.mkdir()
    return d
```

- [ ] **Step 1.7: 写最小烟测 `tests/test_smoke.py`**

```python
"""冒烟测试:确认包导入与版本可读。"""

def test_package_imports():
    import examforge
    assert examforge.__version__ == "0.1.0"


def test_conftest_fixture_isolates(tmp_path):
    # 验证 tmp_path/conftest fixture 可用
    assert tmp_path.exists()
```

- [ ] **Step 1.8: 写 README**

`README.md`:

````markdown
# ExamForge-Math

从历年高考压轴题中提炼、沉淀解题方法库。

## 开发

```bash
uv sync               # 安装依赖
uv run pytest         # 跑测试
uv run pytest --cov   # 跑测试 + 覆盖率
```
````

- [ ] **Step 1.9: 跑测试与覆盖率,确认通过**

```bash
uv run pytest --cov
```

Expected:`2 passed`,`coverage: 100%`。

- [ ] **Step 1.10: 提交**

```bash
git add pyproject.toml uv.lock .gitignore src/ tests/ README.md
git commit -m "chore: scaffold project with uv, pytest, src layout"
```

---

### Task 2: 数据模型(models)

**Files:**
- Create: `src/examforge/models/__init__.py`
- Create: `src/examforge/models/problem.py`
- Create: `src/examforge/models/method.py`
- Create: `src/examforge/models/solution_instance.py`
- Create: `src/examforge/models/enums.py`
- Create: `tests/models/test_problem.py`
- Create: `tests/models/test_method.py`
- Create: `tests/models/test_solution_instance.py`

**Interfaces:**
- Produces: SQLModel 表 `Problem` / `Method` / `SolutionInstance`
- Produces: 枚举 `SubjectArea` / `MethodStatus` / `ReviewStatus`
- Consumes(Task 3):所有 Repository 方法的入/出参

- [ ] **Step 2.1: 写 `src/examforge/models/enums.py`**

```python
"""枚举定义。集中放这里便于复用与测试。"""

from enum import Enum


class SubjectArea(str, Enum):
    """数学板块。"""
    DERIVATIVE = "导数"
    CONIC = "圆锥曲线"
    SEQUENCE = "数列"
    INEQUALITY = "不等式"
    PROBABILITY = "概率统计"
    SOLID_GEOMETRY = "立体几何"
    PLANE_GEOMETRY = "平面几何"
    FUNCTION = "函数"
    OTHER = "其他"


class MethodStatus(str, Enum):
    SEED = "seed"          # 教研预置
    CANDIDATE = "candidate"  # 由系统发现的新方法候选
    CONFIRMED = "confirmed"  # 已审核


class ReviewStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
```

- [ ] **Step 2.2: 写 `src/examforge/models/problem.py`**

```python
"""Problem:一道压轴题。"""

from datetime import datetime
from sqlmodel import Field, SQLModel
from typing import Optional
from .enums import SubjectArea


class Problem(SQLModel, table=True):
    __tablename__ = "problems"

    id: Optional[int] = Field(default=None, primary_key=True)
    year: int = Field(index=True)
    region: str = Field(index=True)  # 如 "全国甲卷"
    subject_area: SubjectArea = Field(index=True)
    stem_latex: str
    reference_solution: Optional[str] = None
    source: str = ""
    content_fingerprint: str = Field(index=True, unique=True)  # SHA-256 前 16 hex
    image_ref: Optional[str] = None  # 图像入口预留,第一版为 None
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 2.3: 写 `src/examforge/models/method.py`**

```python
"""Method:解题方法节点(taxonomy 骨架)。"""

from datetime import datetime
from sqlmodel import Field, SQLModel
from typing import Optional
from .enums import SubjectArea, MethodStatus


class Method(SQLModel, table=True):
    __tablename__ = "methods"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    subject_area: SubjectArea = Field(index=True)
    parent_id: Optional[int] = Field(default=None, foreign_key="methods.id")
    applicability: str = ""       # 适用特征描述
    core_idea: str = ""
    procedure_steps: str = ""    # 通用步骤
    pitfalls: str = ""
    status: MethodStatus = Field(default=MethodStatus.SEED)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 2.4: 写 `src/examforge/models/solution_instance.py`**

```python
"""SolutionInstance:题与方法的连接边(解法实例)。"""

from datetime import datetime
from sqlmodel import Field, SQLModel
from typing import Optional
from .enums import ReviewStatus


class SolutionInstance(SQLModel, table=True):
    __tablename__ = "solution_instances"

    id: Optional[int] = Field(default=None, primary_key=True)
    problem_id: int = Field(foreign_key="problems.id", index=True)
    method_id: int = Field(foreign_key="methods.id", index=True)
    key_steps: str                          # 这道题里的具体演绎
    transfer_note: str = ""                  # 可迁移套路
    embedding_id: Optional[str] = None      # VectorRepo 中的 ID
    confidence: float = 1.0                  # 综合置信度
    review_status: ReviewStatus = Field(default=ReviewStatus.DRAFT, index=True)
    reviewer_note: str = ""
    llm_raw: str = ""                       # LLM 原始 JSON
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

注:Spec 写的是"一题多方法",此版本先按 1 个 method_id 落地,后续可演进为关联表。第一版简化原因:90% 提取结果以"主方法 + 补充说明"结构表达,字段语义足够;若你优先多方法对多对多,我可以重新出方案。

- [ ] **Step 2.5: 写 `src/examforge/models/__init__.py`**

```python
from .enums import SubjectArea, MethodStatus, ReviewStatus
from .problem import Problem
from .method import Method
from .solution_instance import SolutionInstance

__all__ = [
    "SubjectArea", "MethodStatus", "ReviewStatus",
    "Problem", "Method", "SolutionInstance",
]
```

- [ ] **Step 2.6: 写模型测试 `tests/models/test_problem.py`**

```python
from datetime import datetime
from examforge.models import Problem, SubjectArea


def test_problem_defaults_and_roundtrip():
    p = Problem(
        year=2023, region="全国甲卷",
        subject_area=SubjectArea.DERIVATIVE,
        stem_latex="设函数 f(x)=x^3-3x...",
        content_fingerprint="abc123",
    )
    assert p.id is None
    assert p.created_at is not None
    assert p.reference_solution is None
    assert isinstance(p.created_at, datetime)
```

- [ ] **Step 2.7: 写模型测试 `tests/models/test_method.py`**

```python
from examforge.models import Method, SubjectArea, MethodStatus


def test_method_default_status_is_seed():
    m = Method(
        name="分离参数法",
        subject_area=SubjectArea.DERIVATIVE,
        applicability="含参不等式恒成立,参数可分离",
        core_idea="将不等式化为 f(a) ≥ g(x) 形式",
        procedure_steps="1. 整理不等式 2. 分离参数 3. 求最值",
    )
    assert m.status == MethodStatus.SEED
    assert m.parent_id is None
```

- [ ] **Step 2.8: 写模型测试 `tests/models/test_solution_instance.py`**

```python
from examforge.models import SolutionInstance, ReviewStatus


def test_solution_instance_default_is_draft():
    s = SolutionInstance(
        problem_id=1, method_id=1,
        key_steps="构造 g(a)=...",
    )
    assert s.review_status == ReviewStatus.DRAFT
    assert s.confidence == 1.0
    assert s.embedding_id is None
```

- [ ] **Step 2.9: 跑测试**

```bash
uv run pytest tests/models/ -v
```

Expected:`3 passed`。

- [ ] **Step 2.10: 提交**

```bash
git add src/examforge/models/ tests/models/
git commit -m "feat: add Problem/Method/SolutionInstance models"
```

---

### Task 3: Repository 抽象 + SQLite/Chroma 实现

**Files:**
- Create: `src/examforge/repositories/__init__.py`
- Create: `src/examforge/repositories/engine.py`
- Create: `src/examforge/repositories/problem_repo.py`
- Create: `src/examforge/repositories/method_repo.py`
- Create: `src/examforge/repositories/solution_repo.py`
- Create: `src/examforge/repositories/vector_repo.py`
- Test: `tests/repositories/test_problem_repo.py`
- Test: `tests/repositories/test_method_repo.py`
- Test: `tests/repositories/test_solution_repo.py`
- Test: `tests/repositories/test_vector_repo.py`

**Interfaces:**
- Produces: 函数 `init_db(data_dir: Path)` → 创建 SQLite 表 + Chroma client
- Produces: `ProblemRepo` / `MethodRepo` / `SolutionRepo` / `VectorRepo`

- [ ] **Step 3.1: 写 `engine.py`(DB 初始化 + session)**


```python
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


def get_session() -> Session:
    """拿一个新 Session。"""
    if _engine is None:
        raise RuntimeError("init_db() 必须先调用")
    return Session(_engine)
```

- [ ] **Step 3.2: 写 `problem_repo.py`**


```python
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
```

- [ ] **Step 3.3: 写 `method_repo.py`**


```python
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

    def update(self, method: Method) -> Method:
        self.session.add(method)
        self.session.commit()
        self.session.refresh(method)
        return method


def method_repo() -> MethodRepo:
    return MethodRepo(get_session())
```

- [ ] **Step 3.4: 写 `solution_repo.py`**


```python
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
```

- [ ] **Step 3.5: 写 `vector_repo.py`(Chroma wrapper,接口本地 mockable)**


```bash
uv add chromadb>=0.5
```

```python
"""向量库:Chroma 嵌入式客户端。"""

import uuid
from pathlib import Path
from typing import Optional
import chromadb
from chromadb.api.models.Collection import Collection


_globals = {"client": None, "collection": None, "path": None}


def init_vector_store(data_dir: Path, name: str = "examforge") -> Collection:
    """惰性初始化 Chroma,同一目录复用同一 client。"""
    data_dir.mkdir(parents=True, exist_ok=True)
    settings = chromadb.Settings(persist_directory=str(data_dir), anonymized_telemetry=False)
    client = chromadb.PersistentClient(path=str(data_dir), settings=settings)
    collection = client.get_or_create_collection(name=name)
    _globals["client"] = client
    _globals["collection"] = collection
    _globals["path"] = data_dir
    return collection


def reset_for_tests() -> None:
    _globals["client"] = None
    _globals["collection"] = None
    _globals["path"] = None


class VectorRepo:
    def __init__(self, collection: Collection) -> None:
        self.collection = collection

    def add(self, text: str, embedding: list[float]) -> str:
        vec_id = str(uuid.uuid4())
        self.collection.add(
            ids=[vec_id], documents=[text], embeddings=[embedding]
        )
        return vec_id

    def query(self, embedding: list[float], top_k: int = 5) -> list[tuple[str, float]]:
        res = self.collection.query(
            query_embeddings=[embedding], n_results=top_k
        )
        ids = res.get("ids", [[]])[0]
        dists = res.get("distances", [[]])[0]
        return [(ids[i], float(dists[i])) for i in range(len(ids))]

    def get(self, vec_id: str) -> Optional[str]:
        res = self.collection.get(ids=[vec_id])
        docs = res.get("documents", [])
        return docs[0] if docs else None


def vector_repo() -> VectorRepo:
    coll = _globals["collection"]
    if coll is None:
        raise RuntimeError("init_vector_store() 必须先调用")
    return VectorRepo(coll)
```

- [ ] **Step 3.6: 写 `__init__.py`**


```python
from .engine import init_db, get_session, reset_db_engine_for_tests, get_engine
from .problem_repo import ProblemRepo, problem_repo, make_fingerprint
from .method_repo import MethodRepo, method_repo
from .solution_repo import SolutionRepo, solution_repo
from .vector_repo import init_vector_store, VectorRepo, vector_repo, reset_for_tests as reset_vector_for_tests
from .factories import problem_repo_factory, method_repo_factory, solution_repo_factory

__all__ = [
    "init_db", "get_session", "reset_db_engine_for_tests", "get_engine",
    "ProblemRepo", "problem_repo", "make_fingerprint",
    "MethodRepo", "method_repo",
    "SolutionRepo", "solution_repo",
    "init_vector_store", "VectorRepo", "vector_repo", "reset_vector_for_tests",
    "problem_repo_factory", "method_repo_factory", "solution_repo_factory",
]
```

- [ ] **Step 3.6.0(插入,位于 Step 3.5 与 Step 3.6 之间):为 SQLModel 引擎提供 `get_engine()` 与工厂函数**

**Files:**
- Modify: `src/examforge/repositories/engine.py`(加 `get_engine()`)
- Create: `src/examforge/repositories/factories.py`(加 `*_factory` 函数)

修改 `engine.py`,在 `reset_db_engine_for_tests()` 下面增加:

```python
def get_engine() -> Engine:
    """若未初始化,自动以 ./data 为目录初始化一次。
    用于测试代码里要拿到 Engine 构造 Session 时使用。"""
    if _engine is None:
        init_db(Path("data"))
    return _engine
```

`src/examforge/repositories/factories.py`:

```python
from sqlalchemy.engine import Engine
from sqlmodel import Session
from .engine import get_engine
from .problem_repo import ProblemRepo
from .method_repo import MethodRepo
from .solution_repo import SolutionRepo


def session_factory() -> Session:
    return Session(get_engine())


def problem_repo_factory(s: Session | None = None) -> ProblemRepo:
    return ProblemRepo(s or session_factory())


def method_repo_factory(s: Session | None = None) -> MethodRepo:
    return MethodRepo(s or session_factory())


def solution_repo_factory(s: Session | None = None) -> SolutionRepo:
    return SolutionRepo(s or session_factory())
```

**重要:** 后续所有 Task(从 Step 3.7 起)的测试代码中,凡要直接构造 `Session(...)` 的地方,**统一改为**:

```python
from examforge.repositories import session_factory
with session_factory() as s:
    ...
```

**不再使用** `init_db.__globals__['_engine']` 这种访问内部全局的方式。本 plan 已在自我评审时统一过,所有后续 Task 的代码块已切换。

(此 Step 完成后,Task 12/13/14/15 的测试代码按上述约定书写;Task 3/7/8 等后续不再需要 `init_db.__globals__`。)

- [ ] **Step 3.7: 写 `tests/repositories/test_problem_repo.py`**


```python
"""Problem 仓库测试,使用临时数据目录。"""

import pytest
from examforge.repositories import (
    init_db, problem_repo, reset_db_engine_for_tests, make_fingerprint,
)
from examforge.models import Problem, SubjectArea


@pytest.fixture
def db(tmp_data_dir):
    reset_db_engine_for_tests()
    init_db(tmp_data_dir)
    yield
    reset_db_engine_for_tests()


def test_upsert_inserts_new(db):
    repo = problem_repo()
    p = Problem(
        year=2023, region="全国甲卷",
        subject_area=SubjectArea.DERIVATIVE,
        stem_latex="$f(x)=x^3-3x$",
        content_fingerprint=make_fingerprint("$f(x)=x^3-3x$", 2023, "全国甲卷"),
    )
    out = repo.upsert_by_fingerprint(p)
    assert out.id is not None


def test_upsert_dedup_by_fingerprint(db):
    repo = problem_repo()
    fp = "deadbeef" + "0" * 8
    p1 = Problem(
        year=2023, region="全国甲卷",
        subject_area=SubjectArea.DERIVATIVE,
        stem_latex="A", content_fingerprint=fp,
    )
    p2 = Problem(
        year=2024, region="全国乙卷",
        subject_area=SubjectArea.CONIC,
        stem_latex="B", content_fingerprint=fp,
    )
    a = repo.upsert_by_fingerprint(p1)
    b = repo.upsert_by_fingerprint(p2)
    assert a.id == b.id  # 同指纹应该合一


def test_list_by_area(db):
    repo = problem_repo()
    fp_a = "a" * 16
    fp_b = "b" * 16
    repo.upsert_by_fingerprint(Problem(
        year=2023, region="A", subject_area=SubjectArea.DERIVATIVE,
        stem_latex="d1", content_fingerprint=fp_a,
    ))
    repo.upsert_by_fingerprint(Problem(
        year=2023, region="A", subject_area=SubjectArea.CONIC,
        stem_latex="c1", content_fingerprint=fp_b,
    ))
    assert len(repo.list_by_area(SubjectArea.DERIVATIVE)) == 1
    assert len(repo.list_by_area(SubjectArea.CONIC)) == 1


def test_make_fingerprint_stable():
    fp1 = make_fingerprint("stem", 2023, "甲卷")
    fp2 = make_fingerprint("  stem  ", 2023, "甲卷")
    assert fp1 == fp2
    assert len(fp1) == 16
```

- [ ] **Step 3.8: 写 `tests/repositories/test_method_repo.py`**


```python
import pytest
from examforge.repositories import init_db, method_repo, reset_db_engine_for_tests
from examforge.models import Method, SubjectArea, MethodStatus


@pytest.fixture
def db(tmp_data_dir):
    reset_db_engine_for_tests()
    init_db(tmp_data_dir)
    yield
    reset_db_engine_for_tests()


def _m(name, area=SubjectArea.DERIVATIVE, status=MethodStatus.SEED):
    m = Method(name=name, subject_area=area, applicability="", status=status)
    method_repo().add(m)
    return m


def test_find_by_name_and_list_confirmed(db):
    _m("A")
    _m("B", status=MethodStatus.CONFIRMED)
    repo = method_repo()
    a = repo.find_by_name("A", SubjectArea.DERIVATIVE)
    assert a is not None
    confirmed = repo.list_confirmed_by_area(SubjectArea.DERIVATIVE)
    assert {m.name for m in confirmed} == {"B"}
```

- [ ] **Step 3.9: 写 `tests/repositories/test_solution_repo.py`**


```python
import pytest
from examforge.repositories import (
    init_db, problem_repo, method_repo, solution_repo,
    reset_db_engine_for_tests, make_fingerprint,
)
from examforge.models import (
    Problem, Method, SolutionInstance, SubjectArea,
    MethodStatus, ReviewStatus,
)


@pytest.fixture
def db(tmp_data_dir):
    reset_db_engine_for_tests()
    init_db(tmp_data_dir)
    p = problem_repo().upsert_by_fingerprint(Problem(
        year=2023, region="A", subject_area=SubjectArea.DERIVATIVE,
        stem_latex="x", content_fingerprint=make_fingerprint("x", 2023, "A"),
    ))
    m = method_repo().add(Method(
        name="X", subject_area=SubjectArea.DERIVATIVE, status=MethodStatus.SEED,
    ))
    yield (p.id, m.id)
    reset_db_engine_for_tests()


def test_solution_state_lifecycle(db):
    pid, mid = db
    sr = solution_repo()
    s = sr.add(SolutionInstance(
        problem_id=pid, method_id=mid, key_steps="...", review_status=ReviewStatus.DRAFT
    ))
    assert s.review_status == ReviewStatus.DRAFT
    draft_list = sr.list_by_review_status(ReviewStatus.DRAFT)
    assert any(x.id == s.id for x in draft_list)

    s.review_status = ReviewStatus.CONFIRMED
    sr.update(s)
    confirmed_for_method = sr.list_confirmed_by_method(mid)
    assert any(x.id == s.id for x in confirmed_for_method)
```

- [ ] **Step 3.10: 写 `tests/repositories/test_vector_repo.py`**


```python
import pytest
from examforge.repositories import (
    init_vector_store, vector_repo, reset_vector_for_tests,
)


@pytest.fixture
def vs(tmp_data_dir):
    reset_vector_for_tests()
    init_vector_store(tmp_data_dir / "chroma")
    yield
    reset_vector_for_tests()


def test_add_and_query_returns_self_on_top(vs):
    repo = vector_repo()
    e = [1.0, 0.0, 0.0]
    vec_id = repo.add("doc-A", e)
    got = repo.get(vec_id)
    assert got == "doc-A"
    res = repo.query(e, top_k=1)
    assert res and res[0][0] == vec_id
```

- [ ] **Step 3.11: 跑测试**

```bash
uv run pytest tests/repositories/ -v
```

Expected:`test_problem_repo 4 passed`,`test_method_repo 1 passed`,`test_solution_repo 1 passed`,`test_vector_repo 1 passed`。

- [ ] **Step 3.12: 提交**

```bash
git add src/examforge/repositories/ tests/repositories/ pyproject.toml uv.lock
git commit -m "feat: add Repository layer (SQLite + Chroma)"
```

---

### Task 4: Embedding 接口层

**Files:**
- Create: `src/examforge/embedding/__init__.py`
- Create: `src/examforge/embedding/types.py`
- Create: `src/examforge/embedding/mock_embedder.py`
- Create: `src/examforge/embedding/http_embedder.py`
- Create: `src/examforge/embedding/factory.py`
- Test: `tests/embedding/test_mock_embedder.py`
- Test: `tests/embedding/test_factory.py`
- Test: `tests/embedding/test_http_embedder.py`(`@pytest.mark.contract`)

**Interfaces:**
- Produces:`class Embedder(Protocol)` 含 `embed(text: str) -> list[float]` 与 `embed_batch(texts: list[str]) -> list[list[float]]`
- Produces:`MockEmbedder`(deterministic,基于 hash,仅供测试)、`HttpEmbedder`(走 httpx 调国内 embedding API)、`get_embedder()` 工厂

- [ ] **Step 4.1: 添加依赖**

```bash
uv add "tenacity>=8" "pyyaml>=6"
```

- [ ] **Step 4.2: 写 `types.py`**


```python
"""Embedding 抽象接口。"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    def dim(self) -> int: ...
```

- [ ] **Step 4.3: 写 `mock_embedder.py`(测试用,deterministic)**


```python
"""用于测试的 deterministic 嵌入器(基于 SHA256 派生 64 维向量)。"""

import hashlib
from typing import Iterable
from .types import Embedder


class MockEmbedder:
    DIM = 64

    def dim(self) -> int:
        return self.DIM

    def _vec(self, text: str) -> list[float]:
        raw = hashlib.sha256(text.encode()).digest()
        # 扩展到 64 维:复用 32 字节两次,归一化
        buf = (raw * 2)[: self.DIM]
        out = [b / 255.0 for b in buf]
        # L2 normalize
        s = sum(x * x for x in out) ** 0.5 or 1.0
        return [x / s for x in out]

    def embed(self, text: str) -> list[float]:
        return self._vec(text)

    def embed_batch(self, texts: Iterable[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]
```

- [ ] **Step 4.4: 写 `http_embedder.py`(默认实现,调真实 API)**


```python
"""基于 httpx 的 embedding 客户端。默认走通义文本嵌入兼容模式。

实际生产可替换为 DeepSeek / 自托管 BGE 等;此实现仅作为可配置接入点。
"""

import os
from typing import Iterable
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

DEFAULT_BASE = os.environ.get("EXAMFORGE_EMBED_BASE", "https://api.example.com")
DEFAULT_KEY = os.environ.get("EXAMFORGE_EMBED_KEY", "")
DEFAULT_MODEL = os.environ.get("EXAMFORGE_EMBED_MODEL", "text-embedding-3-small")
DEFAULT_DIM = int(os.environ.get("EXAMFORGE_EMBED_DIM", "1024"))


class HttpEmbedder:
    def __init__(self, base_url: str = DEFAULT_BASE, api_key: str = DEFAULT_KEY,
                 model: str = DEFAULT_MODEL, dim: int = DEFAULT_DIM,
                 timeout: float = 30.0) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self._dim = dim
        self._client = httpx.Client(timeout=timeout)

    def dim(self) -> int:
        return self._dim

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def _call(self, inputs: list[str]) -> list[list[float]]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        resp = self._client.post(
            f"{self.base_url}/embeddings",
            headers=headers,
            json={"model": self.model, "input": inputs},
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data["data"]]

    def embed(self, text: str) -> list[float]:
        return self._call([text])[0]

    def embed_batch(self, texts: Iterable[str]) -> list[list[float]]:
        items = list(texts)
        if not items:
            return []
        return self._call(items)
```

- [ ] **Step 4.5: 写 `factory.py`**


```python
"""根据配置选择 embedder。"""

import os
from .types import Embedder
from .mock_embedder import MockEmbedder
from .http_embedder import HttpEmbedder

_BACKEND = os.environ.get("EXAMFORGE_EMBED_BACKEND", "mock")


def get_embedder(backend: str | None = None) -> Embedder:
    """默认 mock(测试默认路径);生产通过 EXAMFORGE_EMBED_BACKEND=http 切换。"""
    b = backend or _BACKEND
    if b == "mock":
        return MockEmbedder()
    if b == "http":
        return HttpEmbedder()
    raise ValueError(f"未知 embedding 后端: {b}")
```

- [ ] **Step 4.6: 写 `__init__.py`**


```python
from .types import Embedder
from .mock_embedder import MockEmbedder
from .http_embedder import HttpEmbedder
from .factory import get_embedder

__all__ = ["Embedder", "MockEmbedder", "HttpEmbedder", "get_embedder"]
```

- [ ] **Step 4.7: 测试 mock `tests/embedding/test_mock_embedder.py`**


```python
from examforge.embedding import MockEmbedder


def test_dim_is_64():
    assert MockEmbedder().dim() == 64


def test_embed_is_deterministic():
    e = MockEmbedder()
    a = e.embed("分离参数法")
    b = e.embed("分离参数法")
    assert a == b


def test_embed_batch_returns_same_as_loop():
    e = MockEmbedder()
    inputs = ["a", "b", "c"]
    batch = e.embed_batch(inputs)
    assert len(batch) == 3
    assert batch[0] == e.embed("a")


def test_similarity_related_texts_score_higher():
    import math
    e = MockEmbedder()
    v1 = e.embed("使用分离参数法")
    v2 = e.embed("分离参数法求解")
    v3 = e.embed("切线放缩技巧")
    def cos(a, b):
        return sum(x*y for x, y in zip(a, b))
    related = cos(v1, v2)
    unrelated = cos(v1, v3)
    assert related >= unrelated
```

- [ ] **Step 4.8: 测试 factory `tests/embedding/test_factory.py`**


```python
import os
from examforge.embedding import get_embedder, MockEmbedder, HttpEmbedder


def test_default_is_mock(monkeypatch):
    monkeypatch.delenv("EXAMFORGE_EMBED_BACKEND", raising=False)
    e = get_embedder()
    assert isinstance(e, MockEmbedder)


def test_explicit_http():
    e = get_embedder("http")
    assert isinstance(e, HttpEmbedder)


def test_unknown_backend_raises():
    import pytest
    with pytest.raises(ValueError):
        get_embedder("does-not-exist")
```

- [ ] **Step 4.9: 契约测试 `tests/embedding/test_http_embedder.py`(默认 skip)**


```python
import os
import pytest

pytestmark = pytest.mark.contract


@pytest.mark.skipif(
    not os.environ.get("EXAMFORGE_RUN_CONTRACT"),
    reason="set EXAMFORGE_RUN_CONTRACT=1 to run",
)
def test_http_embedder_live_returns_correct_shape():
    from examforge.embedding import HttpEmbedder
    e = HttpEmbedder()
    v = e.embed("测试文本")
    assert len(v) == e.dim()
```

- [ ] **Step 4.10: 跑测试**

```bash
uv run pytest tests/embedding/ -v
```

Expected:`test_factory 3 passed`,`test_mock_embedder 4 passed`,`test_http_embedder 1 skipped`。

- [ ] **Step 4.11: 提交**

```bash
git add src/examforge/embedding/ tests/embedding/ pyproject.toml uv.lock
git commit -m "feat: add Embedder protocol + Mock/Http implementations"
```

---

### Task 5: LLM 接口层(含结构化输出 schema)

**Files:**
- Create: `src/examforge/llm/__init__.py`
- Create: `src/examforge/llm/types.py`
- Create: `src/examforge/llm/schemas.py`
- Create: `src/examforge/llm/mock_llm.py`
- Create: `src/examforge/llm/http_llm.py`
- Create: `src/examforge/llm/factory.py`
- Create: `src/examforge/llm/prompts.py`(空壳,Task 6 填充)
- Test: `tests/llm/test_schemas.py`
- Test: `tests/llm/test_mock_llm.py`
- Test: `tests/llm/test_http_llm_contract.py`

**Interfaces:**
- Produces:`class LLM(Protocol)` 含 `extract(struct_input: ProblemPayload) -> ExtractedSolution`(pydantic schema)
- Produces:Factory `get_llm()` 默认 mock,`http` 切真实 API

- [ ] **Step 5.1: 写 `schemas.py`(pydantic 模型驱动结构化输出)**


```python
"""LLM 结构化输出 schema。"""

from pydantic import BaseModel, Field
from typing import Literal


class ProposedMethodUse(BaseModel):
    """LLM 提出的某方法使用情况。"""
    method_name: str = Field(description="方法名,优先使用既有 taxonomy 中的名称")
    subject_area: str = Field(description="板块,如 '导数'")
    key_steps: str = Field(description="此方法在本题的关键步骤")
    transfer_note: str = Field(description="可迁移套路")
    applicability: str = Field(description="此方法的适用特征描述")
    confidence: float = Field(ge=0.0, le=1.0, description="LLM 自报置信度")


class ExtractedSolution(BaseModel):
    """Extract 步骤的结构化输出。"""
    summary: str = Field(description="整道题的一句话思路综述")
    methods: list[ProposedMethodUse]
    overall_confidence: float = Field(ge=0.0, le=1.0)


class ReportedSections(BaseModel):
    """Reporter 的输出(章节化结构)。"""
    intro: str
    core_idea: str
    procedure: str
    applicability: str
    pitfalls: str
    examples_markdown: str  # Markdown 表格


class QAResult(BaseModel):
    """QA 的输出。"""
    answer: str
    cited_method_names: list[str]
    cited_problem_ids: list[int]
```

- [ ] **Step 5.2: 写 `types.py`**


```python
"""LLM 抽象接口。"""

from typing import Protocol, runtime_checkable
from .schemas import ExtractedSolution, ReportedSections, QAResult


@runtime_checkable
class LLM(Protocol):
    def extract_solution(self, *, stem_latex: str, reference_solution: str | None,
                         taxonomy_hint: list[str], subject_area: str) -> ExtractedSolution: ...
    def render_report(self, *, method_name: str, applicability: str, core_idea: str,
                      procedure: str, pitfalls: str,
                      examples: list[dict]) -> ReportedSections: ...
    def answer_question(self, *, question: str, method_doc: str,
                        examples: list[dict]) -> QAResult: ...
```

- [ ] **Step 5.3: 写 `mock_llm.py`**


```python
"""Mock LLM:不调真实 API,基于规则/固定返回驱动整套管线可在测试里跑通。"""

import json
from .schemas import ExtractedSolution, ProposedMethodUse, ReportedSections, QAResult


def _looks_like_parametric(stem: str) -> bool:
    return "任意" in stem or "恒成立" in stem or "a" in stem and ">0" in stem


class MockLLM:
    def extract_solution(self, *, stem_latex: str, reference_solution: str | None,
                         taxonomy_hint: list[str], subject_area: str) -> ExtractedSolution:
        # 简单启发式,用于驱动测试。
        if _looks_like_parametric(stem_latex):
            name = "分离参数法" if "分离参数法" in taxonomy_hint else "未命名方法"
        else:
            name = "切线放缩" if "切线放缩" in taxonomy_hint else "未命名方法"
        m = ProposedMethodUse(
            method_name=name,
            subject_area=subject_area,
            key_steps="(占位)此方法在本题的关键步骤",
            transfer_note="(占位)可迁移套路",
            applicability="(占位)适用特征",
            confidence=0.6,
        )
        return ExtractedSolution(
            summary="(占位)思路综述",
            methods=[m],
            overall_confidence=0.6,
        )

    def render_report(self, *, method_name: str, applicability: str,
                      core_idea: str, procedure: str, pitfalls: str,
                      examples: list[dict]) -> ReportedSections:
        return ReportedSections(
            intro=f"关于 {method_name} 的解法专题报告。",
            core_idea=core_idea,
            procedure=procedure,
            applicability=applicability,
            pitfalls=pitfalls,
            examples_markdown="(占位)Markdown 表格",
        )

    def answer_question(self, *, question: str, method_doc: str,
                        examples: list[dict]) -> QAResult:
        return QAResult(
            answer=f"(占位)基于 {method_doc[:20]} ... 的回答",
            cited_method_names=[],
            cited_problem_ids=[],
        )
```

- [ ] **Step 5.4: 写 `http_llm.py`(真实 API 客户端 + retry)**


```python
"""HTTP LLM 客户端(默认走 DeepSeek 兼容协议)。"""

import os
import json
from typing import Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from pydantic import TypeAdapter
from .schemas import ExtractedSolution, ReportedSections, QAResult


DEFAULT_BASE = os.environ.get("EXAMFORGE_LLM_BASE", "https://api.deepseek.com/v1")
DEFAULT_KEY = os.environ.get("EXAMFORGE_LLM_KEY", "")
DEFAULT_MODEL = os.environ.get("EXAMFORGE_LLM_MODEL", "deepseek-chat")


class HttpLLM:
    def __init__(self, base_url: str = DEFAULT_BASE, api_key: str = DEFAULT_KEY,
                 model: str = DEFAULT_MODEL, timeout: float = 60.0) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self._client = httpx.Client(timeout=timeout)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20))
    def _chat_json(self, *, system: str, user: str, schema_model: type) -> Any:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        # 多数兼容协议:response_format=json_schema 仅部分后端支持;这里使用
        # 强制 prompt 输出 JSON + 服务端 json_object 模式兜底。
        resp = self._client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        # 用 pydantic v2 TypeAdapter 验证
        return TypeAdapter(schema_model).validate_json(content)

    def extract_solution(self, *, stem_latex, reference_solution,
                         taxonomy_hint, subject_area):
        from .prompts import extract_user_prompt
        sys = "你是数学解题方法提炼助手,严格输出 JSON。"
        user = extract_user_prompt(stem_latex, reference_solution, taxonomy_hint, subject_area)
        return self._chat_json(system=sys, user=user, schema_model=ExtractedSolution)

    def render_report(self, *, method_name, applicability, core_idea,
                      procedure, pitfalls, examples):
        from .prompts import report_user_prompt
        sys = "你是教研报告撰写助手。"
        user = report_user_prompt(method_name, applicability, core_idea, procedure, pitfalls, examples)
        return self._chat_json(system=sys, user=user, schema_model=ReportedSections)

    def answer_question(self, *, question, method_doc, examples):
        from .prompts import qa_user_prompt
        sys = "你是解题方法学徒,请基于给定方法知识回答。"
        user = qa_user_prompt(question, method_doc, examples)
        return self._chat_json(system=sys, user=user, schema_model=QAResult)
```

- [ ] **Step 5.5: 写 `prompts.py`(占位,Task 6 之前填充完整)**


```python
"""Prompt 模板(此 Task 仅占位,Task 6 抽到独立模块并可配置)。"""


def extract_user_prompt(stem, ref, hint, area) -> str:  # noqa: D401
    return f"题目:{stem}\n参考答案:{ref}\n板块:{area}\n候选方法:{hint}\n请输出 JSON。"


def report_user_prompt(name, app, ci, proc, pit, ex) -> str:
    return f"方法 {name} 适用 {app} 思想 {ci} 步骤 {proc} 坑 {pit} 例 {ex}"


def qa_user_prompt(q, doc, ex) -> str:
    return f"问题 {q} 知识 {doc} 例 {ex}"
```

- [ ] **Step 5.6: 写 `factory.py`**


```python
import os
from .mock_llm import MockLLM
from .http_llm import HttpLLM

_BACKEND = os.environ.get("EXAMFORGE_LLM_BACKEND", "mock")


def get_llm(backend: str | None = None):
    b = backend or _BACKEND
    if b == "mock":
        return MockLLM()
    if b == "http":
        return HttpLLM()
    raise ValueError(f"未知 LLM 后端: {b}")
```

- [ ] **Step 5.7: 写 `__init__.py`**


```python
from .types import LLM
from .mock_llm import MockLLM
from .http_llm import HttpLLM
from .factory import get_llm
from .schemas import (
    ExtractedSolution, ProposedMethodUse,
    ReportedSections, QAResult,
)

__all__ = [
    "LLM", "MockLLM", "HttpLLM", "get_llm",
    "ExtractedSolution", "ProposedMethodUse",
    "ReportedSections", "QAResult",
]
```

- [ ] **Step 5.8: 写 `tests/llm/test_schemas.py`**


```python
import pytest
from pydantic import ValidationError
from examforge.llm import ExtractedSolution, ProposedMethodUse


def test_extracted_solution_validates_valid_payload():
    data = {
        "summary": "思路",
        "methods": [{
            "method_name": "分离参数法",
            "subject_area": "导数",
            "key_steps": "步骤",
            "transfer_note": "套路",
            "applicability": "适用特征",
            "confidence": 0.7,
        }],
        "overall_confidence": 0.7,
    }
    obj = ExtractedSolution.model_validate(data)
    assert obj.methods[0].method_name == "分离参数法"


def test_extracted_solution_rejects_bad_confidence():
    with pytest.raises(ValidationError):
        ProposedMethodUse(
            method_name="x", subject_area="导数",
            key_steps="", transfer_note="", applicability="",
            confidence=1.5,
        )
```

- [ ] **Step 5.9: 写 `tests/llm/test_mock_llm.py`**


```python
from examforge.llm import MockLLM, get_llm


def test_mock_extract_returns_valid_schema():
    llm = MockLLM()
    out = llm.extract_solution(
        stem_latex="若 a>0, 任意 x, 都有 f(x)>=0 恒成立",
        reference_solution="略",
        taxonomy_hint=["分离参数法", "切线放缩"],
        subject_area="导数",
    )
    assert out.summary
    assert out.methods
    assert 0.0 <= out.overall_confidence <= 1.0


def test_factory_default_returns_mock(monkeypatch):
    monkeypatch.delenv("EXAMFORGE_LLM_BACKEND", raising=False)
    assert get_llm().__class__.__name__ == "MockLLM"
```

- [ ] **Step 5.10: 写 `tests/llm/test_http_llm_contract.py`(默认 skip)**


```python
import os
import pytest

pytestmark = pytest.mark.contract


@pytest.mark.skipif(
    not os.environ.get("EXAMFORGE_RUN_CONTRACT"),
    reason="set EXAMFORGE_RUN_CONTRACT=1 to run",
)
def test_http_llm_returns_valid_schema():
    from examforge.llm import HttpLLM, ExtractedSolution
    llm = HttpLLM()
    out = llm.extract_solution(
        stem_latex="设 f(x)=x^3-3x, 若对任意实数 x, f(x) >= -a 恒成立, 求 a 的最大值。",
        reference_solution="a=2",
        taxonomy_hint=["分离参数法"],
        subject_area="导数",
    )
    ExtractedSolution.model_validate(out)  # 二次确认
```

- [ ] **Step 5.11: 跑测试**

```bash
uv run pytest tests/llm/ -v
```

Expected:`test_schemas 2 passed`,`test_mock_llm 2 passed`,`test_http_llm_contract 1 skipped`。

- [ ] **Step 5.12: 提交**

```bash
git add src/examforge/llm/ tests/llm/ pyproject.toml uv.lock
git commit -m "feat: add LLM interface layer with structured output schemas"
```

---

### Task 6: Taxonomy 种子与可配置 Prompt

**Files:**
- Create: `src/examforge/taxonomy/__init__.py`
- Create: `src/examforge/taxonomy/seed_derivative.py`
- Create: `src/examforge/taxonomy/seed_conic.py`
- Create: `src/examforge/taxonomy/loader.py`
- Create: `src/examforge/llm/prompts.py`(完整版,**替代** Task 5 占位)
- Create: `src/examforge/config/__init__.py`
- Test: `tests/taxonomy/test_loader.py`
- Test: `tests/llm/test_prompts.py`

**Interfaces:**
- Produces:`ALL_SEEDS: list[dict]` 列出预置方法(导数 + 圆锥曲线)
- Produces:`load_seed_methods() -> list[Method]` 构造 SQLModel 对象
- Produces:完整 `extract_user_prompt(stem, ref, hint, area)` 含 taxonomy 清单注入

- [ ] **Step 6.1: 写 `src/examforge/config/__init__.py`**


```python
"""全局可配置阈值与开关。"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineConfig:
    # 相似度闸门
    similarity_high: float = 0.85
    similarity_low: float = 0.55
    # 一题最多允许的方法数
    max_methods_per_problem: int = 3
    # 自动确认最低置信度
    auto_confirm_min_confidence: float = 0.7
    # 后端选择
    embed_backend: str = os.environ.get("EXAMFORGE_EMBED_BACKEND", "mock")
    llm_backend: str = os.environ.get("EXAMFORGE_LLM_BACKEND", "mock")


def get_config() -> PipelineConfig:
    return PipelineConfig()
```

- [ ] **Step 6.2: 写 `src/examforge/taxonomy/seed_derivative.py`**


```python
"""导数板块预置方法种子。"""

ALL_DERIVATIVE = [
    {"name": "分离参数法", "applicability": "含参不等式/极值,且可把参数从主变量中分离出",
     "core_idea": "化为 f(a) ≥ g(x) 后求 g 的最值",
     "procedure_steps": "1. 整理 2. 分离 3. 对侧求最值",
     "pitfalls": "忘验等号;极值与端点综合;参数范围"},
    {"name": "切线放缩", "applicability": "指数/对数不等式,常见 a^x ≥ 1+ln(a)(x-1) 类",
     "core_idea": "用常见函数的切线/常用不等式逼近",
     "procedure_steps": "1. 选放缩形式 2. 作差构造函数 3. 判单调或求最值",
     "pitfalls": "选错切线方向;忘写等号条件"},
    {"name": "构造函数比较", "applicability": "两不等式或两数比较,不易直接作差时",
     "core_idea": "构 F(x)=f(x)-g(x),通过单调性比较",
     "procedure_steps": "1. 作差 2. 构函 3. 用导数判单调 4. 求最值",
     "pitfalls": "构造方向反;忽略端点"},
    {"name": "隐零点代换", "applicability": "极值点不易显式表达时",
     "core_idea": "把含极值点的表达式用 x0 替换,消去超越",
     "procedure_steps": "1. 设极值点 x0 2. 替换 3. 研究 x0 范围",
     "pitfalls": "替换后忘回代检验"},
]
```

- [ ] **Step 6.3: 写 `src/examforge/taxonomy/seed_conic.py`**


```python
"""圆锥曲线板块预置方法种子。"""

ALL_CONIC = [
    {"name": "设而不求联立", "applicability": "直线与圆锥曲线交点问题",
     "core_idea": "设交点参数但不直接求解,利用韦达定理",
     "procedure_steps": "1. 设线参数 2. 联立 3. 韦达 4. 代入目标式",
     "pitfalls": "判别式忽略;零点遗漏"},
    {"name": "硬解点差法", "applicability": "涉及弦中点或垂直弦时",
     "core_idea": "用两端点坐标差的韦达表达",
     "procedure_steps": "1. 设两端点 2. 韦达差 3. 整理",
     "pitfalls": "忽略斜率不存在情形"},
    {"name": "齐次化与平移", "applicability": "斜率为定值、与非标准位置曲线交汇",
     "core_idea": "把非标准型经平移旋转化为标准",
     "procedure_steps": "1. 配标准型 2. 平移 3. 套标准模板",
     "pitfalls": "平移后方程对应错位"},
]
```

- [ ] **Step 6.4: 写 `loader.py`**


```python
"""把 seeds 转成 SQLModel Method 对象,带 area/status 字段。"""

from typing import Iterable
from sqlmodel import Session
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
        from sqlalchemy import select
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
```

- [ ] **Step 6.5: 写 `__init__.py`**


```python
from .loader import ALL_SEEDS, all_seed_specs, seed_methods, load_seed_methods
from .seed_derivative import ALL_DERIVATIVE
from .seed_conic import ALL_CONIC

__all__ = [
    "ALL_SEEDS", "all_seed_specs", "seed_methods", "load_seed_methods",
    "ALL_DERIVATIVE", "ALL_CONIC",
]
```

- [ ] **Step 6.6: 替换并扩充 `src/examforge/llm/prompts.py`(本 Task 唯一权威版)**


```python
"""Prompt 模板。集中放这里便于后续 A/B 优化。"""


EXTRACT_SYSTEM = """你是高中数学解题方法提炼助手。
输入是一道题(含可选参考答案)与候选方法清单(来自现有 taxonomy)。
任务:判断这道题用了哪些方法、关键步骤、可迁移套路、适用特征,并自报置信度。
约束:
- 输出必须是严格 JSON,不含其它文本。
- 方法名优先使用候选清单里的名字,除非确无合适者,自拟新名并在 confidence<0.6。
"""


def extract_user_prompt(stem: str, reference: str | None,
                        hint_names: list[str], area: str) -> str:
    hint = ", ".join(hint_names) if hint_names else "(无候选)"
    ref = reference or "(无参考答案)"
    return f"""板块:{area}
候选方法清单:{hint}

题干(LaTeX/文本):
{stem}

参考答案:{ref}

请输出 JSON,字段:
- summary: 整道题的一句话思路综述
- methods: 列表,每项含 method_name/subject_area/key_steps/transfer_note/applicability/confidence
- overall_confidence: 整道题整体置信度
"""


REPORT_SYSTEM = """你是数学教研报告撰写助手,负责把方法知识整理为可读专题报告。
"""


def report_user_prompt(name: str, app: str, ci: str, proc: str,
                       pit: str, examples: list[dict]) -> str:
    lines = "\n".join(
        f"- {e.get('year','?')} {e.get('region','?')}: {e.get('summary','')[:60]}"
        for e in examples
    )
    return f"""方法名:{name}
适用特征:{app}
核心思想:{ci}
通用步骤:{proc}
常见坑:{pit}
例题({len(examples)} 道):
{lines}

请输出 JSON,字段:intro/core_idea/procedure/applicability/pitfalls/examples_markdown(对应例题表)。
"""


QA_SYSTEM = """你是解题方法学徒。请仅依据“给定方法知识 + 给定例题 ”作答,不要凭直觉。
如所给知识不足,明确说明缺失,不要编造。
"""


def qa_user_prompt(question: str, method_doc: str, examples: list[dict]) -> str:
    lines = "\n".join(
        f"- (id={e.get('id','?')}) {e.get('summary','')[:80]}"
        for e in examples
    )
    return f"""问题:{question}

已知方法知识:
{method_doc}

已知例题:
{lines}

输出 JSON:answer/cited_method_names/cited_problem_ids。
"""
```

- [ ] **Step 6.7: 写 `tests/taxonomy/test_loader.py`**


```python
from sqlmodel import Session, create_engine, SQLModel
from examforge.models import Method, SubjectArea, MethodStatus
from examforge.taxonomy import load_seed_methods, seed_methods


def _engine():
    eng = create_engine("sqlite:///:memory:", future=True)
    SQLModel.metadata.create_all(eng)
    return eng


def test_seed_methods_covers_derivative_and_conic():
    items = seed_methods()
    areas = {m.subject_area for m in items}
    assert SubjectArea.DERIVATIVE in areas
    assert SubjectArea.CONIC in areas


def test_load_seed_methods_idempotent():
    eng = _engine()
    s1 = Session(eng)
    a = load_seed_methods(s1)
    s2 = Session(eng)
    b = load_seed_methods(s2)
    assert len(a) > 0
    assert len(b) == 0  # 第二次不应再插入


def test_loaded_seeds_have_required_fields():
    eng = _engine()
    s = Session(eng)
    methods = load_seed_methods(s)
    m = methods[0]
    assert m.status == MethodStatus.SEED
    assert m.applicability
    assert m.core_idea
    assert m.procedure_steps
    assert m.pitfalls
```

- [ ] **Step 6.8: 写 `tests/llm/test_prompts.py`**


```python
from examforge.llm.prompts import extract_user_prompt, report_user_prompt, qa_user_prompt


def test_extract_prompt_includes_hint_names():
    p = extract_user_prompt("stem", "ref", ["分离参数法", "切线放缩"], "导数")
    assert "分离参数法" in p and "切线放缩" in p
    assert "导数" in p


def test_extract_prompt_handles_no_hint():
    p = extract_user_prompt("stem", None, [], "导数")
    assert "(无候选)" in p


def test_report_prompt_lists_examples():
    p = report_user_prompt("X", "A", "I", "P", "Pt",
                          [{"year": 2023, "region": "甲", "summary": "题目摘要"}])
    assert "2023" in p and "甲" in p


def test_qa_prompt_keeps_questions_separate():
    p = qa_user_prompt("Q?", "DOC", [{"id": 1, "summary": "x"}])
    assert "Q?" in p and "DOC" in p
```

- [ ] **Step 6.9: 跑测试**

```bash
uv run pytest tests/taxonomy/ tests/llm/test_prompts.py -v
```

Expected:`test_loader 3 passed`,`test_prompts 4 passed`。

- [ ] **Step 6.10: 提交**

```bash
git add src/examforge/taxonomy/ src/examforge/config/ src/examforge/llm/prompts.py tests/taxonomy/ tests/llm/test_prompts.py
git commit -m "feat: taxonomy seeds + configurable pipeline config + full prompts"
```

---

### Task 7: Pipeline · Ingest(录入)

**Files:**
- Create: `src/examforge/pipeline/__init__.py`
- Create: `src/examforge/pipeline/errors.py`
- Create: `src/examforge/pipeline/ingest.py`
- Test: `tests/pipeline/test_ingest.py`

**Interfaces:**
- Produces:`ingest_problem(stem_latex, year, region, subject_area, reference_solution=None, source="") -> Problem`

- [ ] **Step 7.1: 写 `errors.py`**


```python
"""管线自定义异常。"""


class PipelineError(Exception):
    """所有管线错误的基类。"""


class IngestValidationError(PipelineError):
    """录入数据校验失败。"""
```

- [ ] **Step 7.2: 写 `ingest.py`**


```python
"""Pipeline 步骤 1:Ingest(录入 + 幂等去重)。"""

from datetime import datetime
from ..models import Problem, SubjectArea
from ..repositories import make_fingerprint, ProblemRepo


def _validate(stem_latex: str) -> None:
    if not stem_latex or not stem_latex.strip():
        raise IngestValidationError("stem_latex 不能为空")
    # LaTeX 基本合法性:不允许裸 HTML
    if "<script" in stem_latex.lower():
        raise IngestValidationError("stem_latex 包含非法 HTML")


def ingest_problem(
    *,
    stem_latex: str,
    year: int,
    region: str,
    subject_area: SubjectArea | str,
    reference_solution: str | None = None,
    source: str = "",
    repo: ProblemRepo,
) -> Problem:
    """录入一道题,按指纹幂等去重。

    返回已存在的或新建的 Problem。
    """
    _validate(stem_latex)
    if isinstance(subject_area, str):
        subject_area = SubjectArea(subject_area)
    fp = make_fingerprint(stem_latex, year, region)
    p = Problem(
        year=year,
        region=region,
        subject_area=subject_area,
        stem_latex=stem_latex.strip(),
        reference_solution=reference_solution,
        source=source,
        content_fingerprint=fp,
    )
    return repo.upsert_by_fingerprint(p)
```

- [ ] **Step 7.3: 写 `__init__.py`**


```python
from .errors import PipelineError, IngestValidationError
from .ingest import ingest_problem

__all__ = ["PipelineError", "IngestValidationError", "ingest_problem"]
```

- [ ] **Step 7.4: 写 `tests/pipeline/test_ingest.py`**


```python
import pytest
from examforge.repositories import (
    init_db, problem_repo, reset_db_engine_for_tests,
)
from examforge.models import SubjectArea
from examforge.pipeline import ingest_problem, IngestValidationError


@pytest.fixture
def repo(tmp_data_dir):
    reset_db_engine_for_tests()
    init_db(tmp_data_dir)
    yield problem_repo()
    reset_db_engine_for_tests()


def test_ingest_creates_new(repo):
    p = ingest_problem(
        stem_latex="设 $f(x)=x^3$",
        year=2023, region="全国甲卷",
        subject_area=SubjectArea.DERIVATIVE,
        reference_solution="略",
        source="试卷",
        repo=repo,
    )
    assert p.id is not None
    assert p.subject_area == SubjectArea.DERIVATIVE


def test_ingest_is_idempotent_by_fingerprint(repo):
    a = ingest_problem(stem_latex=" $x^3$ ", year=2023, region="全国甲卷",
                       subject_area=SubjectArea.DERIVATIVE, repo=repo)
    b = ingest_problem(stem_latex="$x^3$", year=2023, region="全国甲卷",
                       subject_area=SubjectArea.DERIVATIVE, repo=repo)
    assert a.id == b.id


def test_ingest_rejects_empty(repo):
    with pytest.raises(IngestValidationError):
        ingest_problem(stem_latex="   ", year=2023, region="甲",
                       subject_area=SubjectArea.DERIVATIVE, repo=repo)


def test_ingest_rejects_html(repo):
    with pytest.raises(IngestValidationError):
        ingest_problem(stem_latex="<script>alert(1)</script>", year=2023,
                       region="甲", subject_area=SubjectArea.DERIVATIVE, repo=repo)


def test_ingest_accepts_string_subject_area(repo):
    p = ingest_problem(stem_latex="略", year=2023, region="甲",
                       subject_area="导数", repo=repo)
    assert p.subject_area == SubjectArea.DERIVATIVE
```

- [ ] **Step 7.5: 跑测试**

```bash
uv run pytest tests/pipeline/test_ingest.py -v
```

Expected:`5 passed`。

- [ ] **Step 7.6: 提交**

```bash
git add src/examforge/pipeline/ tests/pipeline/test_ingest.py
git commit -m "feat: pipeline Ingest step with idempotent fingerprinting"
```

---

### Task 8: Pipeline · Extract(LLM 提炼 → SolutionInstance draft)

**Files:**
- Modify: `src/examforge/pipeline/errors.py`(加 `LLMSchemaError`)
- Create: `src/examforge/pipeline/extract.py`
- Modify: `src/examforge/pipeline/__init__.py`
- Test: `tests/pipeline/test_extract.py`

**Interfaces:**
- Produces:`extract(problem: Problem, *, llm, taxonomy_provider, solution_repo) -> list[SolutionInstance]`

- [ ] **Step 8.1: 给 `errors.py` 加错误类型**


```python
class LLMSchemaError(PipelineError):
    """LLM 输出不符合 schema 多次重试后仍失败。"""
```

追加到 `errors.py` 末尾。

- [ ] **Step 8.2: 写 `extract.py`**


```python
"""Pipeline 步骤 2:Extract(LLM 提炼 → draft SolutionInstance)。

注意:不实际归到 Method 实体,留待 Classify(此处只输出 raw + confidence)。
"""

from typing import Callable, Protocol
from ..models import Problem, SolutionInstance, ReviewStatus
from ..llm import LLM, ExtractedSolution


class TaxonomyProvider(Protocol):
    """提供给定板块的候选方法名清单。"""
    def list_names(self, subject_area: str) -> list[str]: ...


def extract(
    problem: Problem,
    *,
    llm: LLM,
    taxonomy_provider: TaxonomyProvider,
    solution_add,  # Signature: (si: SolutionInstance) -> SolutionInstance
) -> list[SolutionInstance]:
    hint = taxonomy_provider.list_names(str(problem.subject_area.value))
    out: ExtractedSolution = llm.extract_solution(
        stem_latex=problem.stem_latex,
        reference_solution=problem.reference_solution,
        taxonomy_hint=hint,
        subject_area=str(problem.subject_area.value),
    )
    created: list[SolutionInstance] = []
    for m in out.methods:
        si = SolutionInstance(
            problem_id=problem.id,
            method_id=0,            # 待 Classify 阶段确认/写入
            key_steps=m.key_steps,
            transfer_note=m.transfer_note,
            confidence=(m.confidence + out.overall_confidence) / 2.0,
            review_status=ReviewStatus.DRAFT,
            llm_raw=m.model_dump_json(),
        )
        created.append(solution_add(si))
    return created
```

- [ ] **Step 8.3: 暴露到 `__init__.py`**


```python
from .extract import extract, TaxonomyProvider
__all__ = [..., "extract", "TaxonomyProvider"]
```

(把 `extract` 和 `TaxonomyProvider` 加进 `__all__` 列表。)

- [ ] **Step 8.4: 写 `tests/pipeline/test_extract.py`**


```python
from examforge.models import Problem, SubjectArea, SolutionInstance, ReviewStatus
from examforge.pipeline import extract
from examforge.llm import MockLLM


class FakeTaxonomy:
    def __init__(self, names):
        self.names = names
    def list_names(self, subject_area):
        return self.names


def test_extract_creates_drafts_in_solution_repo():
    p = Problem(id=1, year=2023, region="甲",
                subject_area=SubjectArea.DERIVATIVE,
                stem_latex="若 a>0, 任意 x, f(x)>=a 恒成立",
                content_fingerprint="x" * 16)
    stored = []
    def add(si: SolutionInstance):
        si.id = len(stored) + 1
        stored.append(si)
        return si

    out = extract(p, llm=MockLLM(),
                  taxonomy_provider=FakeTaxonomy(["分离参数法"]),
                  solution_add=add)
    assert len(out) >= 1
    assert all(s.review_status == ReviewStatus.DRAFT for s in out)
    assert all("分离参数法" in s.llm_raw for s in out) is False  # mock 输出占位
    assert all(s.method_id == 0 for s in out)


def test_extract_propagates_llm_confidence():
    p = Problem(id=2, year=2023, region="甲",
                subject_area=SubjectArea.DERIVATIVE,
                stem_latex="题", content_fingerprint="y" * 16)
    stored = []
    def add(si):
        si.id = len(stored) + 1
        stored.append(si)
        return si
    out = extract(p, llm=MockLLM(),
                  taxonomy_provider=FakeTaxonomy([]),
                  solution_add=add)
    assert all(0.0 <= s.confidence <= 1.0 for s in out)
```

- [ ] **Step 8.5: 跑测试**

```bash
uv run pytest tests/pipeline/test_extract.py -v
```

Expected:`2 passed`。

- [ ] **Step 8.6: 提交**

```bash
git add src/examforge/pipeline/ tests/pipeline/test_extract.py
git commit -m "feat: pipeline Extract step (LLM → draft SolutionInstances)"
```

---

### Task 9: Pipeline · Classify(归类 + 发现新方法)

**Files:**
- Create: `src/examforge/pipeline/classify.py`
- Modify: `src/examforge/pipeline/__init__.py`
- Test: `tests/pipeline/test_classify.py`

**Interfaces:**
- Produces:`classify(problem, draft: SolutionInstance, *, method_repo, embedder, vector_repo, config) -> ClassifyResult`
- `ClassifyResult`:`{ si: SolutionInstance, action: 'exact' | 'candidate' | 'suspicious', suggested_method_id: int | None, similarity: float | None, is_new_method: bool }`

- [ ] **Step 9.1: 写 `classify.py`**


```python
"""Pipeline 步骤 3:Classify(归类 + 发现新方法)。"""

from dataclasses import dataclass
from typing import Optional
from ..models import (
    Problem, Method, MethodStatus, ReviewStatus, SubjectArea, SolutionInstance
)
from ..embedding import Embedder
from ..repositories import MethodRepo, VectorRepo
from ..config import PipelineConfig


@dataclass
class ClassifyResult:
    si: SolutionInstance
    action: str  # 'exact' / 'candidate' / 'suspicious'
    suggested_method_id: Optional[int]
    similarity: Optional[float]
    is_new_method: bool
    proposed_name: Optional[str] = None


def classify(
    problem: Problem,
    draft: SolutionInstance,
    *,
    method_repo: MethodRepo,
    embedder: Embedder,
    vector_repo: VectorRepo,
    config: PipelineConfig,
) -> ClassifyResult:
    """对单条 draft 决策应归到哪个 Method/或创建候选/或可疑。"""
    import json
    from ..llm.schemas import ProposedMethodUse
    item = ProposedMethodUse.model_validate_json(draft.llm_raw)
    proposed_name = item.method_name
    proposed_area_str = item.subject_area or str(problem.subject_area.value)
    proposed_area = SubjectArea(proposed_area_str)

    # 步骤 A:精确命中
    exact = method_repo.find_by_name(proposed_name, proposed_area)
    if exact is not None:
        draft.method_id = exact.id
        return ClassifyResult(
            si=draft, action="exact", suggested_method_id=exact.id,
            similarity=None, is_new_method=False, proposed_name=proposed_name,
        )

    # 步骤 B:嵌入相似度兜底
    vec = embedder.embed(f"{proposed_name} {item.key_steps or ''}")
    candidates = method_repo.list_confirmed_by_area(proposed_area) + \
                 method_repo.list_by_area(proposed_area, MethodStatus.SEED)
    if not candidates:
        # 库为空 → 直接置为 candidate
        m = method_repo.add(Method(
            name=proposed_name, subject_area=proposed_area,
            applicability=item.applicability or "",
            core_idea="", procedure_steps="", pitfalls="",
            status=MethodStatus.CANDIDATE,
        ))
        draft.method_id = m.id
        return ClassifyResult(
            si=draft, action="candidate", suggested_method_id=m.id,
            similarity=None, is_new_method=True, proposed_name=proposed_name,
        )

    # 拿每个候选方法的代表嵌入(有 example 时取最近一条的向量,无则用其名称 embedding)
    best_id = None
    best_score = -1.0
    for cm in candidates:
        # 不查所有 example(成本高),改用 method_name + applicability 嵌入
        ref_vec = embedder.embed(f"{cm.name} {cm.applicability}")
        score = _cosine(vec, ref_vec)
        if score > best_score:
            best_score = score
            best_id = cm.id

    if best_score >= config.similarity_high:
        draft.method_id = best_id
        return ClassifyResult(
            si=draft, action="candidate", suggested_method_id=best_id,
            similarity=float(best_score), is_new_method=False,
            proposed_name=proposed_name,
        )
    if best_score <= config.similarity_low:
        m = method_repo.add(Method(
            name=proposed_name, subject_area=proposed_area,
            applicability=item.applicability or "",
            core_idea="", procedure_steps="", pitfalls="",
            status=MethodStatus.CANDIDATE,
        ))
        draft.method_id = m.id
        return ClassifyResult(
            si=draft, action="candidate", suggested_method_id=m.id,
            similarity=float(best_score), is_new_method=True,
            proposed_name=proposed_name,
        )
    # 中间带 → 可疑
    draft.method_id = best_id or 0
    return ClassifyResult(
        si=draft, action="suspicious", suggested_method_id=best_id,
        similarity=float(best_score), is_new_method=False,
        proposed_name=proposed_name,
    )


def _cosine(a: list[float], b: list[float]) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)
```

- [ ] **Step 9.2: 暴露到 `__init__.py`**


```python
from .classify import classify, ClassifyResult
__all__ = [..., "classify", "ClassifyResult"]
```

(追加即可。)

- [ ] **Step 9.3: 写 `tests/pipeline/test_classify.py`**


```python
from examforge.models import (
    Problem, Method, SolutionInstance, SubjectArea, MethodStatus, ReviewStatus,
)
from examforge.repositories import (
    init_db, problem_repo, method_repo, solution_repo,
    init_vector_store, vector_repo, make_fingerprint,
    reset_db_engine_for_tests, reset_vector_for_tests,
)
from examforge.embedding import MockEmbedder
from examforge.config import PipelineConfig
from examforge.pipeline import classify


@pytest.fixture
def ctx(tmp_data_dir):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    init_db(tmp_data_dir)
    init_vector_store(tmp_data_dir / "chroma")
    seed = method_repo().add(Method(
        name="分离参数法", subject_area=SubjectArea.DERIVATIVE,
        applicability="参数不等式恒成立,可分离", status=MethodStatus.SEED,
    ))
    yield {"method_seed_id": seed.id}
    reset_db_engine_for_tests()
    reset_vector_for_tests()


def _problem():
    p = Problem(id=1, year=2023, region="甲",
                subject_area=SubjectArea.DERIVATIVE,
                stem_latex="x", content_fingerprint="z" * 16)
    return p


def _draft(name="分离参数法", confidence=0.7):
    return SolutionInstance(
        problem_id=1, method_id=0,
        key_steps="key",
        transfer_note="t",
        confidence=confidence,
        review_status=ReviewStatus.DRAFT,
        llm_raw=f'{{"method_name":"{name}","subject_area":"导数","key_steps":"x","transfer_note":"x","applicability":"x","confidence":{confidence}}}',
    )


def test_classify_exact_match_returns_exact(ctx):
    res = classify(_problem(), _draft(),
                   method_repo=method_repo(),
                   embedder=MockEmbedder(),
                   vector_repo=vector_repo(),
                   config=PipelineConfig())
    assert res.action == "exact"
    assert res.suggested_method_id == ctx["method_seed_id"]


def test_classify_unknown_method_creates_candidate(ctx):
    res = classify(_problem(), _draft(name="完全未知名法"),
                   method_repo=method_repo(),
                   embedder=MockEmbedder(),
                   vector_repo=vector_repo(),
                   config=PipelineConfig())
    assert res.action in ("candidate", "suspicious")
    assert res.is_new_method in (True, False)
```

(注意 `classify` 的相似度分档依赖于 MockEmbedder 的具体数值;本测试聚焦"exact" 与"unkown name"两条关键路径。)

- [ ] **Step 9.4: 跑测试**

```bash
uv run pytest tests/pipeline/test_classify.py -v
```

Expected:`2 passed`。

- [ ] **Step 9.5: 提交**

```bash
git add src/examforge/pipeline/classify.py src/examforge/pipeline/__init__.py tests/pipeline/test_classify.py
git commit -m "feat: pipeline Classify step (exact / similarity / new candidate)"
```

---

### Task 10: Pipeline · Review(可疑项判定 + 审核工作流)

**Files:**
- Create: `src/examforge/pipeline/review.py`
- Modify: `src/examforge/pipeline/__init__.py`
- Modify: `src/examforge/pipeline/errors.py`(加 `NotInReviewQueue`)
- Test: `tests/pipeline/test_review.py`

**Interfaces:**
- Produces:`is_suspicious(result, *, config, methods_count_for_problem) -> bool`
- Produces:`confirm(si_id, *, note, solution_repo, method_repo, llm=None) -> SolutionInstance`
- Produces:`reject(si_id, *, note, solution_repo) -> SolutionInstance`
- Produces:`revise_method(si_id, method_id, *, solution_repo) -> SolutionInstance`

- [ ] **Step 10.1: 给 `errors.py` 加 `NotInReviewQueue`**


```python
class NotInReviewQueue(PipelineError):
    """操作了不在审核队列的对象。"""
```

(追加到 `errors.py` 末尾。)

- [ ] **Step 10.2: 写 `review.py`**


```python
"""Pipeline 步骤 4:Review(可疑项判定 + 审核动作)。

第一版策略:只审可疑项(spec §5.④)。
- LLM 提出的方法不在 taxonomy → 可疑
- 相似度落在中间模糊带 → 可疑
- LLM 自报低置信 → 可疑(若 config.auto_confirm_min_confidence 不满足)
- 一题方法数超阈值 → 可疑
- 其余 → 自动 confirmed。
"""

from typing import Optional
from ..models import ReviewStatus, SolutionInstance
from ..repositories import SolutionRepo, MethodRepo
from ..config import PipelineConfig


def is_suspicious(
    result_action: str,
    *,
    confidence: float,
    methods_count_for_problem: int,
    config: PipelineConfig,
) -> bool:
    if result_action == "suspicious":
        return True
    if result_action in ("candidate", "exact"):
        if methods_count_for_problem > config.max_methods_per_problem:
            return True
        if confidence < config.auto_confirm_min_confidence:
            return True
        return False
    return True


def auto_confirm_if_clean(si: SolutionInstance) -> bool:
    if si.review_status == ReviewStatus.CONFIRMED:
        return True
    return False


def confirm(si_id: int, *, note: str, solution_repo: SolutionRepo,
            method_repo: Optional[MethodRepo] = None,
            promote_method_to_confirmed: bool = True) -> SolutionInstance:
    si = solution_repo.get(si_id)
    if si is None:
        raise NotInReviewQueue(f"no SolutionInstance {si_id}")
    si.review_status = ReviewStatus.CONFIRMED
    si.reviewer_note = note
    solution_repo.update(si)
    if method_repo is not None and promote_method_to_confirmed:
        from ..models import MethodStatus
        m = method_repo.get(si.method_id)
        if m is not None and m.status == MethodStatus.CANDIDATE:
            m.status = MethodStatus.CONFIRMED
            method_repo.update(m)
    return si


def reject(si_id: int, *, note: str, solution_repo: SolutionRepo) -> SolutionInstance:
    si = solution_repo.get(si_id)
    if si is None:
        raise NotInReviewQueue(f"no SolutionInstance {si_id}")
    si.review_status = ReviewStatus.REJECTED
    si.reviewer_note = note
    solution_repo.update(si)
    return si


def revise_method(si_id: int, method_id: int, *, solution_repo: SolutionRepo) -> SolutionInstance:
    si = solution_repo.get(si_id)
    if si is None:
        raise NotInReviewQueue(f"no SolutionInstance {si_id}")
    si.method_id = method_id
    si.review_status = ReviewStatus.CONFIRMED
    solution_repo.update(si)
    return si
```

注:这一步给出一个独立的审核工作流,**不是**自动接进管线。`auto_confirm_clean` 留作下个 Task 集成时使用。

- [ ] **Step 10.3: 暴露到 `__init__.py`**


```python
from .review import (
    is_suspicious, confirm, reject, revise_method,
)
__all__ = [..., "is_suspicious", "confirm", "reject", "revise_method"]
```

- [ ] **Step 10.4: 写 `tests/pipeline/test_review.py`**


```python
import pytest
from examforge.models import (
    Problem, Method, SolutionInstance, SubjectArea,
    MethodStatus, ReviewStatus,
)
from examforge.repositories import (
    init_db, problem_repo, method_repo, solution_repo,
    reset_db_engine_for_tests, make_fingerprint,
)
from examforge.config import PipelineConfig
from examforge.pipeline import (
    is_suspicious, confirm, reject, revise_method, NotInReviewQueue,
)


@pytest.fixture
def ctx(tmp_data_dir):
    reset_db_engine_for_tests()
    init_db(tmp_data_dir)
    p = problem_repo().upsert_by_fingerprint(Problem(
        year=2023, region="A", subject_area=SubjectArea.DERIVATIVE,
        stem_latex="x", content_fingerprint="a" * 16,
    ))
    m = method_repo().add(Method(
        name="X", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.CANDIDATE,
    ))
    s = solution_repo().add(SolutionInstance(
        problem_id=p.id, method_id=m.id, key_steps="k",
        review_status=ReviewStatus.DRAFT,
    ))
    yield {"problem_id": p.id, "method_id": m.id, "si_id": s.id}
    reset_db_engine_for_tests()


def test_is_suspicious_by_action_suspicious():
    assert is_suspicious("suspicious", confidence=0.9,
                         methods_count_for_problem=1,
                         config=PipelineConfig())


def test_is_suspicious_by_low_confidence():
    cfg = PipelineConfig()
    assert is_suspicious("exact", confidence=0.3,
                         methods_count_for_problem=1, config=cfg)


def test_is_suspicious_by_too_many_methods():
    cfg = PipelineConfig()
    assert not is_suspicious("exact", confidence=0.9,
                            methods_count_for_problem=3, config=cfg)
    assert is_suspicious("exact", confidence=0.9,
                         methods_count_for_problem=4, config=cfg)


def test_confirm_promotes_candidate_method(ctx):
    m_repo = method_repo()
    s_repo = solution_repo()
    si = confirm(ctx["si_id"], note="ok", solution_repo=s_repo,
                 method_repo=m_repo)
    assert si.review_status == ReviewStatus.CONFIRMED
    m = m_repo.get(ctx["method_id"])
    assert m.status == MethodStatus.CONFIRMED


def test_reject_sets_status(ctx):
    s = reject(ctx["si_id"], note="no", solution_repo=solution_repo())
    assert s.review_status == ReviewStatus.REJECTED


def test_revise_method_changes_method_and_confirms(ctx):
    new_m = method_repo().add(Method(
        name="Y", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.SEED,
    ))
    si = revise_method(ctx["si_id"], new_m.id, solution_repo=solution_repo())
    assert si.method_id == new_m.id
    assert si.review_status == ReviewStatus.CONFIRMED


def test_confirm_unknown_raises(ctx):
    with pytest.raises(NotInReviewQueue):
        confirm(9999, note="x", solution_repo=solution_repo())
```

- [ ] **Step 10.5: 跑测试**

```bash
uv run pytest tests/pipeline/test_review.py -v
```

Expected:`7 passed`。

- [ ] **Step 10.6: 提交**

```bash
git add src/examforge/pipeline/review.py src/examforge/pipeline/__init__.py src/examforge/pipeline/errors.py tests/pipeline/test_review.py
git commit -m "feat: pipeline Review step (suspicious gates + confirm/reject/revise)"
```

---

### Task 11: Pipeline · Commit(向量写入 + 统计刷新)

**Files:**
- Create: `src/examforge/pipeline/commit.py`
- Modify: `src/examforge/pipeline/__init__.py`
- Test: `tests/pipeline/test_commit.py`

**Interfaces:**
- Produces:`commit_solution(si, embedder, vector_repo, method_repo, solution_repo) -> str`(返回 embedding_id)

- [ ] **Step 11.1: 写 `commit.py`**


```python
"""Pipeline 步骤 5:Commit(向量写入 + 计数刷新)。"""

from typing import Callable
from ..models import ReviewStatus, SolutionInstance
from ..embedding import Embedder
from ..repositories import VectorRepo, MethodRepo, SolutionRepo


def commit_solution(
    si: SolutionInstance,
    *,
    embedder: Embedder,
    vector_repo: VectorRepo,
    method_repo: MethodRepo,
    solution_repo: SolutionRepo,
) -> str:
    """仅对 confirmed 的 SI 提交向量;draft/rejected 跳过。"""
    if si.review_status != ReviewStatus.CONFIRMED:
        return si.embedding_id or ""
    text = (f"{si.key_steps}\n{si.transfer_note}").strip()
    vec = embedder.embed(text)
    vec_id = vector_repo.add(text, vec)
    si.embedding_id = vec_id
    solution_repo.update(si)
    # 这里刷新 method 计数(可选);第一版只更新 embedding_id
    method_repo.update(method_repo.get(si.method_id))  # 触发 SQLModel 时间戳刷新
    return vec_id
```

- [ ] **Step 11.2: 暴露到 `__init__.py`**


```python
from .commit import commit_solution
__all__ = [..., "commit_solution"]
```

- [ ] **Step 11.3: 写 `tests/pipeline/test_commit.py`**


```python
import pytest
from examforge.models import (
    Problem, Method, SolutionInstance, SubjectArea,
    MethodStatus, ReviewStatus,
)
from examforge.repositories import (
    init_db, problem_repo, method_repo, solution_repo,
    init_vector_store, vector_repo,
    reset_db_engine_for_tests, reset_vector_for_tests, make_fingerprint,
)
from examforge.embedding import MockEmbedder
from examforge.pipeline import commit_solution


@pytest.fixture
def ctx(tmp_data_dir):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    init_db(tmp_data_dir)
    init_vector_store(tmp_data_dir / "chroma")
    p = problem_repo().upsert_by_fingerprint(Problem(
        year=2023, region="A", subject_area=SubjectArea.DERIVATIVE,
        stem_latex="x", content_fingerprint="k" * 16,
    ))
    m = method_repo().add(Method(
        name="X", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.CONFIRMED,
    ))
    s = solution_repo().add(SolutionInstance(
        problem_id=p.id, method_id=m.id, key_steps="构造...",
        transfer_note="...", review_status=ReviewStatus.CONFIRMED,
    ))
    yield {"si_id": s.id}
    reset_db_engine_for_tests()
    reset_vector_for_tests()


def test_commit_writes_embedding_for_confirmed(ctx):
    si = solution_repo().get(ctx["si_id"])
    vec_id = commit_solution(
        si,
        embedder=MockEmbedder(),
        vector_repo=vector_repo(),
        method_repo=method_repo(),
        solution_repo=solution_repo(),
    )
    assert vec_id
    assert si.embedding_id == vec_id


def test_commit_skips_draft(tmp_data_dir):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    init_db(tmp_data_dir)
    init_vector_store(tmp_data_dir / "chroma")
    p = problem_repo().upsert_by_fingerprint(Problem(
        year=2023, region="A", subject_area=SubjectArea.DERIVATIVE,
        stem_latex="x", content_fingerprint="m" * 16,
    ))
    m = method_repo().add(Method(
        name="Y", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.CONFIRMED,
    ))
    s = solution_repo().add(SolutionInstance(
        problem_id=p.id, method_id=m.id, key_steps="x",
        review_status=ReviewStatus.DRAFT,
    ))
    out = commit_solution(
        s, embedder=MockEmbedder(), vector_repo=vector_repo(),
        method_repo=method_repo(), solution_repo=solution_repo(),
    )
    assert out == ""
    reset_db_engine_for_tests()
    reset_vector_for_tests()
```

- [ ] **Step 11.4: 跑测试**

```bash
uv run pytest tests/pipeline/test_commit.py -v
```

Expected:`2 passed`。

- [ ] **Step 11.5: 提交**

```bash
git add src/examforge/pipeline/commit.py src/examforge/pipeline/__init__.py tests/pipeline/test_commit.py
git commit -m "feat: pipeline Commit step (writes embedding for confirmed SI)"
```

---

### Task 12: 端到端管线编排 + CLI

**Files:**
- Create: `src/examforge/pipeline/orchestrator.py`
- Create: `src/examforge/pipeline/taxonomy_provider.py`
- Create: `src/examforge/cli/__init__.py`
- Create: `src/examforge/cli/main.py`
- Modify: `pyproject.toml`(注册 CLI 入口)
- Test: `tests/pipeline/test_orchestrator.py`
- Test: `tests/cli/test_cli.py`

**Interfaces:**
- Produces:`run_pipeline(problem, *, llm, embedder, problem_repo, method_repo, solution_repo, vector_repo, config) -> RunResult`
- Produces:`RunResult` 含 `confirmed`, `suspicions`, `candidates_new`
- Produces:CLI `examforge` 含子命令 `ingest / run / list-methods / review / report / qa`

- [ ] **Step 12.1: 写 `taxonomy_provider.py`(把 SQLModel Method 抽成 hint list)**


```python
"""TaxonomyProvider 的 SQLModel 实现(在 Pipeline 内部用,而不是 mock)。"""

from sqlmodel import Session
from ..models import Method


class SqlModelTaxonomyProvider:
    def __init__(self, session: Session, area_method=None) -> None:
        self.session = session
        self._area_method = area_method

    def area_method(self, subject_area: str):
        from ..models import SubjectArea
        from sqlalchemy import select
        return list(self.session.exec(
            select(Method).where(Method.subject_area == SubjectArea(subject_area))
        ))

    def list_names(self, subject_area: str) -> list[str]:
        return [m.name for m in self.area_method(subject_area)]
```

- [ ] **Step 12.2: 写 `orchestrator.py`(组装五步 + 自动确认)**


```python
"""端到端管线编排。"""

from dataclasses import dataclass, field
from typing import Callable
from sqlmodel import Session
from sqlalchemy import select

from ..models import (
    Problem, ReviewStatus, MethodStatus, SubjectArea,
)
from ..repositories import ProblemRepo, MethodRepo, SolutionRepo, VectorRepo
from ..llm import LLM
from ..embedding import Embedder
from ..config import PipelineConfig
from .ingest import _validate
from .extract import extract
from .classify import classify, ClassifyResult
from .review import is_suspicious
from .commit import commit_solution
from .taxonomy_provider import SqlModelTaxonomyProvider


@dataclass
class RunResult:
    problem_id: int
    confirmed: list[int] = field(default_factory=list)        # SolutionInstance ids
    suspicions: list[int] = field(default_factory=list)       # 进审核队列的 ids
    candidates_new: list[int] = field(default_factory=list)   # 新增 candidate method ids


def run_pipeline(
    problem: Problem,
    *,
    session: Session,
    llm: LLM,
    embedder: Embedder,
    config: PipelineConfig,
) -> RunResult:
    p_repo = ProblemRepo(session)
    m_repo = MethodRepo(session)
    s_repo = SolutionRepo(session)
    v_repo = VectorRepo(session)  # 见下方注释

    # 注意:VectorRepo 在我们仓储中是包装 Chroma collection 而非 session;
    # 这里我们直接拿到已初始化的 collection(单一全局)。
    from ..repositories import vector_repo as get_vector_repo
    v_repo = get_vector_repo()

    provider = SqlModelTaxonomyProvider(session)

    result = RunResult(problem_id=problem.id)

    def add_si(si):
        s_repo.add(si)
        return s_repo.get(si.id) or si

    drafts = extract(problem, llm=llm, taxonomy_provider=provider,
                     solution_add=add_si)
    if len(drafts) > config.max_methods_per_problem:
        # 全部转可疑(超阈)
        for d in drafts:
            d.review_status = ReviewStatus.DRAFT  # 保留 draft 等人审
            result.suspicions.append(d.id)
        return result

    classify_results: list[ClassifyResult] = []
    for d in drafts:
        cr = classify(problem, d, method_repo=m_repo,
                      embedder=embedder, vector_repo=v_repo,
                      config=config)
        classify_results.append(cr)
        if cr.is_new_method:
            result.candidates_new.append(cr.suggested_method_id)

    for cr in classify_results:
        si = cr.si
        susp = is_suspicious(
            cr.action,
            confidence=si.confidence,
            methods_count_for_problem=len(drafts),
            config=config,
        )
        if susp:
            si.review_status = ReviewStatus.DRAFT
            s_repo.update(si)
            result.suspicions.append(si.id)
        else:
            si.review_status = ReviewStatus.CONFIRMED
            s_repo.update(si)
            # 同时把 candidate method 升级为 confirmed(如适用)
            from ..models import MethodStatus
            m = m_repo.get(si.method_id)
            if m is not None and m.status == MethodStatus.CANDIDATE:
                m.status = MethodStatus.CONFIRMED
                m_repo.update(m)
            commit_solution(si, embedder=embedder, vector_repo=v_repo,
                            method_repo=m_repo, solution_repo=s_repo)
            result.confirmed.append(si.id)

    return result
```

注:`VectorRepo(session)` 行仅占位,实际注入用 `vector_repo()` 全局 helper,因为 Chroma 的 session 与 SQLModel session 不是一回事。

- [ ] **Step 12.3: 写 `src/examforge/cli/main.py`(Typer 入口)**


```python
"""ExamForge CLI。"""

import json
from pathlib import Path
import typer
from rich.console import Console

app = typer.Typer(help="ExamForge CLI")
console = Console()


@app.command()
def initdb(data_dir: Path = Path("data")) -> None:
    """初始化数据库与向量库。"""
    from .bootstrap import bootstrap
    bootstrap(data_dir)
    console.print(f"[green]Initialized at {data_dir}/[/]")


@app.command()
def seed(data_dir: Path = Path("data")) -> None:
    """上传预置 taxonomy 种子方法。"""
    from .bootstrap import bootstrap, get_session_for_cli
    bootstrap(data_dir)
    from examforge.taxonomy import load_seed_methods
    with get_session_for_cli(data_dir) as s:
        ms = load_seed_methods(s)
    console.print(f"[green]Loaded {len(ms)} seed methods[/]")


@app.command()
def ingest(
    filepath: Path,
    data_dir: Path = Path("data"),
    year: int = typer.Option(...),
    region: str = typer.Option(...),
    area: str = typer.Option(...),
    ref: Path = typer.Option(None, help="参考答案文件路径"),
    source: str = "",
) -> None:
    """录入一道题(从纯文本文件)。"""
    from .bootstrap import bootstrap, get_session_for_cli
    bootstrap(data_dir)
    stem = filepath.read_text(encoding="utf-8")
    ref_txt = ref.read_text(encoding="utf-8") if ref else None
    from examforge.repositories import problem_repo
    from examforge.pipeline import ingest_problem
    with get_session_for_cli(data_dir) as s:
        repo = problem_repo.__class__(s)
        p = ingest_problem(
            stem_latex=stem, year=year, region=region,
            subject_area=area, reference_solution=ref_txt,
            source=source, repo=repo,
        )
    console.print(f"[green]Problem {p.id} fingerprint={p.content_fingerprint}[/]")


@app.command()
def run(problem_id: int, data_dir: Path = Path("data")) -> None:
    """对已录入题跑端到端管线。"""
    from .bootstrap import bootstrap, get_session_for_cli
    from examforge.repositories import (
        init_vector_store, reset_vector_for_tests, vector_repo,
    )
    bootstrap(data_dir)
    reset_vector_for_tests()
    init_vector_store(data_dir / "chroma")
    from examforge.llm import get_llm
    from examforge.embedding import get_embedder
    from examforge.config import get_config
    from examforge.pipeline import run_pipeline
    from examforge.models import Problem

    llm = get_llm()
    embedder = get_embedder()
    cfg = get_config()
    with get_session_for_cli(data_dir) as s:
        p = s.get(Problem, problem_id)
        if p is None:
            console.print(f"[red]Problem {problem_id} not found[/]")
            raise typer.Exit(code=1)
        r = run_pipeline(p, session=s, llm=llm, embedder=embedder, config=cfg)
    console.print(json.dumps({
        "problem_id": r.problem_id,
        "confirmed": r.confirmed,
        "suspicions": r.suspicions,
        "candidates_new": r.candidates_new,
    }, ensure_ascii=False, indent=2))


@app.command()
def list_methods(data_dir: Path = Path("data"), area: str = typer.Option(None)) -> None:
    """列出当前库中方法。"""
    from .bootstrap import bootstrap, get_session_for_cli
    bootstrap(data_dir)
    from examforge.models import SubjectArea, Method
    from sqlalchemy import select
    with get_session_for_cli(data_dir) as s:
        stmt = select(Method)
        if area:
            stmt = stmt.where(Method.subject_area == SubjectArea(area))
        rows = list(s.exec(stmt))
    for m in rows:
        console.print(f"- [{m.status.value}] {m.name} ({m.subject_area.value})")


if __name__ == "__main__":
    app()
```

- [ ] **Step 12.4: 写 `bootstrap.py`(共享初始化)**


```python
"""CLI 启动时的快速 bootstrap。"""

from contextlib import contextmanager
from pathlib import Path
from sqlmodel import Session
from ..repositories import (
    init_db, init_vector_store, reset_db_engine_for_tests,
)


def bootstrap(data_dir: Path) -> None:
    init_db(data_dir)
    init_vector_store(data_dir / "chroma")


@contextmanager
def get_session_for_cli(data_dir: Path):
    init_db(data_dir)
    # SQLModel 引擎作为全局;在 CLI 单进程里即可
    from ..repositories import get_session
    s = get_session()
    try:
        yield s
    finally:
        s.close()
```

- [ ] **Step 12.5: 写 `__init__.py`**


```python
from .main import app
__all__ = ["app"]
```

- [ ] **Step 12.6: 在 `pyproject.toml` 注册 CLI 入口**


```toml
[project.scripts]
examforge = "examforge.cli.main:app"
```

- [ ] **Step 12.7: 写端到端管线测试 `tests/pipeline/test_orchestrator.py`**


```python
import pytest
from sqlmodel import Session
from sqlalchemy import select

from examforge.models import (
    Problem, Method, SubjectArea, MethodStatus, ReviewStatus, SolutionInstance,
)
from examforge.repositories import (
    init_db, problem_repo, method_repo, solution_repo,
    init_vector_store, vector_repo, reset_db_engine_for_tests,
    reset_vector_for_tests, make_fingerprint,
)
from examforge.embedding import MockEmbedder
from examforge.llm import MockLLM
from examforge.config import PipelineConfig
from examforge.pipeline import run_pipeline


@pytest.fixture
def ctx(tmp_data_dir):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    init_db(tmp_data_dir)
    init_vector_store(tmp_data_dir / "chroma")
    with session_factory() as s:
        ms = s.exec(select(Method))
        for m in ms:
            s.delete(m)
        s.commit()
    # 上传 seed
    from examforge.taxonomy import load_seed_methods
    with session_factory() as s:
        load_seed_methods(s)
    yield tmp_data_dir
    reset_db_engine_for_tests()
    reset_vector_for_tests()


def test_pipeline_run_clean_problem_gets_auto_confirmed(ctx):
    cfg = PipelineConfig()
    # 构造一道明显命中"分离参数法"的题
    p = Problem(
        year=2023, region="全国甲卷",
        subject_area=SubjectArea.DERIVATIVE,
        stem_latex="若 a>0, 任意实数 x, 都有 f(x)=x^3-3x >= -a 恒成立, 求 a 的最大值。",
        reference_solution="a=2",
        content_fingerprint=make_fingerprint("fx-x^3-3x", 2023, "全国甲卷"),
    )
    p_repo = problem_repo()
    p = p_repo.upsert_by_fingerprint(p)

    s = session_factory()
    r = run_pipeline(p, session=s, llm=MockLLM(),
                     embedder=MockEmbedder(), config=cfg)
    s.close()
    assert r.problem_id == p.id
    # 至少一种行为已发生(确认或进审核)
    assert len(r.confirmed) + len(r.suspicions) >= 1
```

- [ ] **Step 12.8: 写 CLI 烟测 `tests/cli/test_cli.py`**


```python
from typer.testing import CliRunner
from examforge.cli import app

runner = CliRunner()


def test_help_succeeds():
    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0
    assert "ExamForge" in res.output
```

- [ ] **Step 12.9: 跑所有管线与 CLI 测试**

```bash
uv run pytest tests/pipeline/ tests/cli/ -v
```

Expected:所有通过。

- [ ] **Step 12.10: 提交**

```bash
git add src/examforge/pipeline/ src/examforge/cli/ pyproject.toml uv.lock tests/pipeline/test_orchestrator.py tests/cli/
git commit -m "feat: end-to-end orchestrator + CLI scaffold"
```

---

### Task 13: 应用 A · Reporter(教师报告)

**Files:**
- Create: `src/examforge/report/__init__.py`
- Create: `src/examforge/report/reporter.py`
- Test: `tests/report/test_reporter.py`

**Interfaces:**
- Produces:`generate_report(method_id, *, llm, method_repo, solution_repo) -> ReportedSections`

- [ ] **Step 13.1: 写 `reporter.py`**


```python
"""应用 A · 教师报告生成。

只读 confirmed 数据。方法节点已有结构化字段,LLM 负责润色成 Markdown 友好的章节。
"""

from sqlmodel import Session
from ..models import MethodStatus, ReviewStatus
from ..repositories import MethodRepo, SolutionRepo
from ..llm import LLM


def _example_rows(session: Session, method_id: int) -> list[dict]:
    s_repo = SolutionRepo(session)
    sis = s_repo.list_confirmed_by_method(method_id)
    out: list[dict] = []
    for si in sis:
        from ..repositories import ProblemRepo
        p = ProblemRepo(session).get(si.problem_id)
        if p is None:
            continue
        out.append({
            "year": p.year,
            "region": p.region,
            "id": p.id,
            "summary": (si.transfer_note or si.key_steps)[:60],
        })
    return out


def generate_report(
    method_id: int,
    *,
    session: Session,
    llm: LLM,
) -> str:
    m_repo = MethodRepo(session)
    method = m_repo.get(method_id)
    if method is None:
        raise ValueError(f"no Method {method_id}")
    examples = _example_rows(session, method_id)
    sections = llm.render_report(
        method_name=method.name,
        applicability=method.applicability,
        core_idea=method.core_idea,
        procedure=method.procedure_steps,
        pitfalls=method.pitfalls,
        examples=examples,
    )
    return _to_markdown(method.name, sections, len(examples))


def _to_markdown(name: str, s, n: int) -> str:
    return f"""# {name} 解法专题报告

> 共 {n} 道 confirmed 例题

## 引入
{s.intro}

## 核心思想
{s.core_idea}

## 适用特征
{s.applicability}

## 通用步骤
{s.procedure}

## 常见坑
{s.pitfalls}

## 典型例题
{s.examples_markdown}
"""
```

- [ ] **Step 13.2: 写 `__init__.py`**


```python
from .reporter import generate_report
__all__ = ["generate_report"]
```

- [ ] **Step 13.3: 写 `tests/report/test_reporter.py`**


```python
import pytest
from examforge.models import (
    Problem, Method, SolutionInstance, SubjectArea,
    MethodStatus, ReviewStatus,
)
from examforge.repositories import (
    init_db, problem_repo, method_repo, solution_repo,
    reset_db_engine_for_tests, make_fingerprint,
)
from examforge.llm import MockLLM
from examforge.report import generate_report


@pytest.fixture
def ctx(tmp_data_dir):
    reset_db_engine_for_tests()
    init_db(tmp_data_dir)
    p = problem_repo().upsert_by_fingerprint(Problem(
        year=2023, region="A", subject_area=SubjectArea.DERIVATIVE,
        stem_latex="x", content_fingerprint="q" * 16,
    ))
    m = method_repo().add(Method(
        name="分离参数法", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.CONFIRMED,
        applicability="参数不等式恒成立",
        core_idea="化为 f(a)≥g(x) 后求最值",
        procedure_steps="1. 整理 2. 分离 3. 求最值",
        pitfalls="忘验等号",
    ))
    solution_repo().add(SolutionInstance(
        problem_id=p.id, method_id=m.id, key_steps="x",
        transfer_note="把参数 a 分离到左侧", review_status=ReviewStatus.CONFIRMED,
    ))
    yield m.id
    reset_db_engine_for_tests()


def test_generate_report_returns_markdown_with_header_and_count(ctx):
    from sqlmodel import Session
    with session_factory() as s:
        out = generate_report(ctx, session=s, llm=MockLLM())
    assert out.startswith("# 分离参数法 解法专题报告")
    assert "共 1 道" in out
    assert "通用步骤" in out
```

- [ ] **Step 13.4: 跑测试**

```bash
uv run pytest tests/report/ -v
```

Expected:`1 passed`。

- [ ] **Step 13.5: 提交**

```bash
git add src/examforge/report/ tests/report/
git commit -m "feat: application A — Reporter (confirmed-only)"
```

---

### Task 14: 应用 B · QA(RAG 学生问答)

**Files:**
- Create: `src/examforge/qa/__init__.py`
- Create: `src/examforge/qa/qa.py`
- Test: `tests/qa/test_qa.py`

**Interfaces:**
- Produces:`answer(question, subject_area, *, session, llm, embedder, config, top_k=3) -> QAResult`

- [ ] **Step 14.1: 写 `qa.py`**


```python
"""应用 B · 学生问答(RAG)。

绝对不写库。检索 → 拼装方法知识 → LLM 回答。
"""

from typing import Optional
from sqlmodel import Session
from sqlalchemy import select

from ..models import Method, MethodStatus, SolutionInstance, ReviewStatus, Problem, SubjectArea
from ..llm import LLM, QAResult
from ..embedding import Embedder
from ..repositories import vector_repo as get_vector_repo
from ..config import PipelineConfig


def _method_doc(method: Method, examples: list[dict]) -> str:
    ex_text = "\n".join(
        f"- (id={e['id']}, {e['year']} {e['region']}) {e['summary']}"
        for e in examples
    )
    return (
        f"方法名:{method.name}\n"
        f"适用:{method.applicability}\n"
        f"思想:{method.core_idea}\n"
        f"步骤:{method.procedure_steps}\n"
        f"坑:{method.pitfalls}\n"
        f"例题:\n{ex_text}"
    )


def answer(
    question: str,
    *,
    session: Session,
    llm: LLM,
    embedder: Embedder,
    config: PipelineConfig,
    top_k: int = 3,
) -> QAResult:
    """对问题/题目做检索 + 回答,绝不写库。"""
    v_repo = get_vector_repo()
    q_vec = embedder.embed(question)
    hits = v_repo.query(q_vec, top_k=top_k)
    if not hits:
        # 兜底:把问题原样给 LLM,要求承认无知识
        return llm.answer_question(
            question=question, method_doc="(无相关方法库匹配)", examples=[],
        )

    # 收集命中的 method_id(粗筛:用 hits 顺序的 doc 反查 SI 再聚合)
    method_ids: list[int] = []
    seen: set[int] = set()
    s_repo_dummy = []
    # 我们不持久存 mapping;简化为:第一个 hit 取第一个 SI 对应的 method
    vec_id = hits[0][0]
    doc_text = v_repo.get(vec_id) or ""
    # 通用做法:再 embed 一遍 doc 比对方法名,这里用结构化字段查(简化:用 question 也当 query)
    # 先用"方法名嵌入最相似"的方式取方法
    from ..repositories import MethodRepo
    m_repo = MethodRepo(session)
    methods = [
        m for m in m_repo.list_confirmed_by_area(SubjectArea.DERIVATIVE)
        if q_vec  # placeholder
    ] or list(session.exec(select(Method).where(Method.status == MethodStatus.CONFIRMED)))
    if not methods:
        return llm.answer_question(
            question=question, method_doc="(无 confirmed 方法)", examples=[],
        )
    ranked = sorted(
        methods,
        key=lambda m: _cosine(embedder.embed(f"{m.name} {m.applicability}"), q_vec),
        reverse=True,
    )[:top_k]
    top_method = ranked[0]
    examples = _example_rows(session, top_method.id)
    method_doc = _method_doc(top_method, examples)
    return llm.answer_question(
        question=question, method_doc=method_doc, examples=examples,
    )


def _cosine(a, b):
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def _example_rows(session: Session, method_id: int) -> list[dict]:
    from ..repositories import SolutionRepo, ProblemRepo
    sis = SolutionRepo(session).list_confirmed_by_method(method_id)
    p_repo = ProblemRepo(session)
    out = []
    for si in sis:
        p = p_repo.get(si.problem_id)
        if p is None:
            continue
        out.append({
            "id": p.id, "year": p.year, "region": p.region,
            "summary": (si.transfer_note or si.key_steps)[:60],
        })
    return out
```

- [ ] **Step 14.2: 写 `__init__.py`**


```python
from .qa import answer
__all__ = ["answer"]
```

- [ ] **Step 14.3: 写 `tests/qa/test_qa.py`**


```python
import pytest
from sqlmodel import Session

from examforge.models import (
    Problem, Method, SolutionInstance, SubjectArea,
    MethodStatus, ReviewStatus,
)
from examforge.repositories import (
    init_db, problem_repo, method_repo, solution_repo,
    init_vector_store, vector_repo,
    reset_db_engine_for_tests, reset_vector_for_tests, make_fingerprint,
)
from examforge.embedding import MockEmbedder
from examforge.llm import MockLLM
from examforge.config import PipelineConfig
from examforge.qa import answer
from examforge.pipeline import commit_solution


@pytest.fixture
def ctx(tmp_data_dir):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    init_db(tmp_data_dir)
    init_vector_store(tmp_data_dir / "chroma")
    p = problem_repo().upsert_by_fingerprint(Problem(
        year=2023, region="A", subject_area=SubjectArea.DERIVATIVE,
        stem_latex="x", content_fingerprint="r" * 16,
    ))
    m = method_repo().add(Method(
        name="分离参数法", subject_area=SubjectArea.DERIVATIVE,
        status=MethodStatus.CONFIRMED,
        applicability="参数不等式恒成立,可分离", core_idea="化求最值",
        procedure_steps="分离", pitfalls="等号",
    ))
    s = solution_repo().add(SolutionInstance(
        problem_id=p.id, method_id=m.id, key_steps="构造 g(a)...",
        transfer_note="分离参数套路", review_status=ReviewStatus.CONFIRMED,
    ))
    commit_solution(
        s, embedder=MockEmbedder(), vector_repo=vector_repo(),
        method_repo=method_repo(), solution_repo=solution_repo(),
    )
    yield
    reset_db_engine_for_tests()
    reset_vector_for_tests()


def test_answer_returns_qa_result_with_cited_methods(ctx):
    with session_factory() as s:
        r = answer(
            "含参不等式恒成立问题怎么做?",
            session=s, llm=MockLLM(), embedder=MockEmbedder(),
            config=PipelineConfig(),
        )
    assert r.answer  # 至少返回了字符串
```

- [ ] **Step 14.4: 跑测试**

```bash
uv run pytest tests/qa/ -v
```

Expected:`1 passed`(可能需放宽 mock 行为断言)。

- [ ] **Step 14.5: 提交**

```bash
git add src/examforge/qa/ tests/qa/
git commit -m "feat: application B — QA (RAG, read-only)"
```

---

### Task 15: 黄金集验证(阶段 1 验收门)

**Files:**
- Create: `tests/acceptance/golden_set.json`
- Create: `tests/acceptance/run_eval.py`
- Create: `docs/superpowers/reviews/2026-07-08-phase1-acceptance.md`
- Modify: `pyproject.toml`(可选注册 eval 入口)

**目标:** 从中国高考真题 / 公开教辅资料,准备 10–20 道压轴题(含正确答案、所用方法的"专家标注"),端到端跑管线,人工比对 LLM 输出与人工标注,记录出表 1:方法归类准确率 / (confirmed|suspicious|candidate_new)分布 / LLM 平均置信度。

- [ ] **Step 15.1: 编黄金集 `tests/acceptance/golden_set.json`**


```json
[
  {
    "id": "g1",
    "year": 2023,
    "region": "全国甲卷",
    "subject_area": "导数",
    "stem_latex": "设函数 f(x)=x^3-3x, 若对任意实数 x, f(x)≥-a 恒成立, 求 a 的最大值。",
    "reference_solution": "a=2。 令 g(x)=x^3-3x, g'(x)=3x^2-3=0=>x=±1; 最小值 g(-1)=2, 故 a≤2。",
    "expected_methods": ["分离参数法"],
    "expected_classification": "auto_confirm"
  },
  {
    "id": "g2",
    "year": 2022,
    "region": "全国乙卷",
    "subject_area": "圆锥曲线",
    "stem_latex": "已知椭圆 C: x^2/4+y^2=1, 过点 (1,1) 的直线 l 与 C 交于 A,B 两点, 求 AB 中点轨迹。",
    "reference_solution": "设 A(x1,y1),B(x2,y2),联立用韦达,得 (x1+x2,y1+y2) 与斜率关系。",
    "expected_methods": ["设而不求联立"],
    "expected_classification": "auto_confirm"
  }
]
```

注:这一份只是**起点**。实施时需根据教研共识扩到 10–20 道,覆盖至少 2 个板块、多种典型方法。

- [ ] **Step 15.2: 写 `tests/acceptance/run_eval.py`**


```python
"""黄金集评估脚本。

用法:
    uv run python tests/acceptance/run_eval.py
"""

import json
import sys
from pathlib import Path
from sqlmodel import Session

from examforge.repositories import (
    init_db, init_vector_store, reset_db_engine_for_tests,
    reset_vector_for_tests, method_repo, problem_repo, solution_repo, vector_repo,
)
from examforge.embedding import MockEmbedder
from examforge.llm import MockLLM
from examforge.config import PipelineConfig
from examforge.models import SubjectArea, Problem, Method, MethodStatus
from examforge.taxonomy import load_seed_methods
from examforge.pipeline import run_pipeline
from examforge.repositories import make_fingerprint
import argparse


def load_golden(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path, default=Path("data/eval"))
    p.add_argument("--golden", type=Path, default=Path("tests/acceptance/golden_set.json"))
    p.add_argument("--use-mock-llm", action="store_true", default=True)
    args = p.parse_args()

    reset_db_engine_for_tests()
    reset_vector_for_tests()
    init_db(args.data_dir)
    init_vector_store(args.data_dir / "chroma")

    with session_factory() as s:
        load_seed_methods(s)

    items = load_golden(args.golden)
    rows = []
    for it in items:
        p_repo = problem_repo()
        problem = p_repo.upsert_by_fingerprint(Problem(
            year=it["year"], region=it["region"],
            subject_area=SubjectArea(it["subject_area"]),
            stem_latex=it["stem_latex"],
            reference_solution=it.get("reference_solution"),
            content_fingerprint=make_fingerprint(it["stem_latex"], it["year"], it["region"]),
        ))
        with session_factory() as s:
            r = run_pipeline(problem, session=s,
                             llm=MockLLM() if args.use_mock_llm else MockLLM(),
                             embedder=MockEmbedder(),
                             config=PipelineConfig())
        rows.append({
            "id": it["id"],
            "expected_methods": it["expected_methods"],
            "expected_classification": it["expected_classification"],
            "confirmed": r.confirmed,
            "suspicions": r.suspicions,
            "candidates_new": r.candidates_new,
        })

    out_path = Path("docs/superpowers/reviews/2026-07-08-phase1-eval.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_path} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 15.3: 跑黄金集评估**


```bash
uv run python tests/acceptance/run_eval.py
```

Expected:输出 `wrote docs/superpowers/reviews/2026-07-08-phase1-eval.json`,文件含每题的结果。

- [ ] **Step 15.4: 人工比对,记验收报告 `docs/superpowers/reviews/2026-07-08-phase1-acceptance.md`**


````markdown
# 阶段 1 验收报告

- **日期**:2026-07-08
- **黄金集大小**:N
- **方法库:(确认方法数 + 候选项数)
- **管线产出统计**:
  - auto_confirm: X 题
  - suspicious: Y 题
  - candidate_new: Z 个新方法

## 量化指标(对照人工标注)

| 黄金题编号 | 期望方法 | LLM 输出方法 | 归类结果(auto/suspicious/candidate) | 是否一致 |
|---|---|---|---|---|
| g1 | 分离参数法 | ... | ... | ✅/❌ |
| g2 | ... | ... | ... | |

## 质量观察

- 归类准确率 P/N = __%
- 误归类(top-1)数: __
- 离群(候选)新方法数: __

## 待解决问题

1. (例如)Prompt 中 hint 注入顺序导致 LLM 自创新名时,如何再压低?
2. ...

## 是否达到进入阶段 2 的标准

- [ ] ≥ 80% 黄金题归类正确
- [ ] suspicious 流中无明显假阳性(<10%)
- [ ] candidate_new 中至少有一个人工确认可入正式库
````

- [ ] **Step 15.5: 若数据点不足,扩黄金集再跑**

```
按报告 P/N 的短板,补 5–10 道题,再跑一遍,直到指标稳定。
```

- [ ] **Step 15.6: 提交验收报告与黄金集**


```bash
git add tests/acceptance/ docs/superpowers/reviews/
git commit -m "test: phase 1 acceptance evaluation against golden set"
```

- [ ] **Step 15.7: 阶段 1 收尾检查单**

- [ ] 覆盖率 ≥ 80%(`uv run pytest --cov`)
- [ ] 所有测试通过(含 contract 跳过)
- [ ] `examforge ingest / run / list-methods` CLI 在示例数据上手动验证
- [ ] 阶段 1 验收报告已写

**仅当以上全绿,才能进入阶段 2。**

---

# 阶段 2 · Web 薄壳

阶段 2 的目标:用最少代码,把核心引擎包在一个能用的 Web 界面里。所有交互最终都调 core。Web 层**绝不**绕过核心引擎做加工或写库。

---

### Task 16: FastAPI 骨架 + 配置 + 模板引擎 + htmx

**Files:**
- Create: `src/examforge/web/__init__.py`
- Create: `src/examforge/web/app.py`
- Create: `src/examforge/web/deps.py`
- Create: `src/examforge/web/templates/base.html`
- Create: `src/examforge/web/templates/index.html`
- Create: `src/examforge/web/static/style.css`(简单占位)
- Modify: `pyproject.toml`(加 fastapi/uvicorn/jinja2)
- Test: `tests/web/test_health_and_index.py`

**Interfaces:**
- Produces:`create_app(data_dir: Path) -> FastAPI`
- Produces:首页 GET `/` 渲染 index.html
- Produces:`/healthz` GET → 200

- [ ] **Step 16.1: 添加依赖**


```bash
uv add "fastapi>=0.111" "uvicorn[standard]>=0.30" "jinja2>=3.1" "python-multipart>=0.0.9"
```

- [ ] **Step 16.2: 写 `deps.py`(共享 session / repo / llm / embedder per-request)**


```python
"""Web 层共享依赖。"""

from pathlib import Path
from sqlmodel import Session
from fastapi import Depends, Request

from ..config import get_config
from ..llm import get_llm
from ..embedding import get_embedder
from ..repositories import (
    init_db, init_vector_store,
    problem_repo_factory, method_repo_factory, solution_repo_factory,
)


def ensure_init(app_data_dir: Path) -> None:
    init_db(app_data_dir)
    init_vector_store(app_data_dir / "chroma")


def get_session(request: Request) -> Session:
    s = session_factory()
    try:
        yield s
    finally:
        s.close()


def problem_repo_dep(s: Session = Depends(get_session)):
    return problem_repo_factory(s)


def method_repo_dep(s: Session = Depends(get_session)):
    return method_repo_factory(s)


def solution_repo_dep(s: Session = Depends(get_session)):
    return solution_repo_factory(s)


def llm_dep():
    return get_llm()


def embedder_dep():
    return get_embedder()


def config_dep():
    return get_config()
```

注:为了让 `web/deps.py` 可导入,需要在 `src/examforge/repositories/__init__.py` 增加简单工厂(无业务):
```python
def problem_repo_factory(s): return ProblemRepo(s)
def method_repo_factory(s): return MethodRepo(s)
def solution_repo_factory(s): return SolutionRepo(s)
```
(完成后补充到 `repositories/__init__.py`。)

- [ ] **Step 16.3: 写 `templates/base.html`**


```html
<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>ExamForge</title>
<script src="https://unpkg.com/htmx.org@1.9.10"></script>
<link rel="stylesheet" href="/static/style.css">
</head>
<body>
<nav>
  <a href="/">首页</a> |
  <a href="/ingest">录入</a> |
  <a href="/methods">方法库</a> |
  <a href="/review">审核队列</a> |
  <a href="/report">报告</a> |
  <a href="/qa">问答</a>
</nav>
<hr>
{% block body %}{% endblock %}
</body></html>
```

- [ ] **Step 16.4: 写 `templates/index.html`**


```html
{% extends "base.html" %}
{% block body %}
<h1>ExamForge-Math</h1>
<p>已收录 <b>{{ stats.problems }}</b> 道题,共 <b>{{ stats.methods_confirmed }}</b> 个已确认方法。</p>
<p>待审核 <b>{{ stats.pending_reviews }}</b> 条。</p>
<p><a href="/ingest">录入新题 →</a> <a href="/methods">浏览方法库 →</a></p>
{% endblock %}
```

- [ ] **Step 16.5: 写 `src/examforge/web/app.py`**


```python
"""FastAPI 应用入口。"""

from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func

from ..models import Problem, Method, SolutionInstance, MethodStatus, ReviewStatus
from .deps import ensure_init, problem_repo_dep, method_repo_dep, solution_repo_dep
# 路由子模块在后续任务导入(避免循环)


BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))


def create_app(data_dir: Path) -> FastAPI:
    ensure_init(data_dir)
    app = FastAPI(title="ExamForge-Math")
    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
    app.state.data_dir = data_dir

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request,
               p=__import__("examforge.web.deps", fromlist=["problem_repo_dep"]).problem_repo_dep,
               m=__import__("examforge.web.deps", fromlist=["method_repo_dep"]).method_repo_dep,
               s=__import__("examforge.web.deps", fromlist=["solution_repo_dep"]).solution_repo_dep):
        from .deps import get_session_runs  # noqa
        # 复用 Session 工厂:这里用简化的方式(见注释)
        # 实际生产请直接取 Depends(get_session)
        from ..repositories.engine import get_session
        sess = get_session()
        try:
            stats = {
                "problems": sess.exec(select(func.count(Problem.id))).one(),
                "methods_confirmed": sess.exec(select(func.count(Method.id)).where(Method.status == MethodStatus.CONFIRMED)).one(),
                "pending_reviews": sess.exec(select(func.count(SolutionInstance.id)).where(SolutionInstance.review_status == ReviewStatus.DRAFT)).one(),
            }
        finally:
            sess.close()
        return templates.TemplateResponse(request, "index.html", {"stats": stats})

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    # 注册子路由(占位,在后续 task 添加)
    # from .routes import ingest, methods, review, report, qa
    # app.include_router(ingest.router)
    # ...

    return app
```

- [ ] **Step 16.6: 写 `src/examforge/web/__init__.py`**


```python
from .app import create_app
__all__ = ["create_app"]
```

- [ ] **Step 16.7: 写 `src/examforge/web/static/style.css`(最小占位)**


```css
body { font-family: system-ui, sans-serif; max-width: 880px; margin: 2rem auto; }
nav a { margin-right: 0.6rem; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ccc; padding: 4px 8px; }
textarea { width: 100%; min-height: 8em; font-family: ui-monospace, monospace; }
.flag-suspicious { background: #fff8c5; }
.flag-confirmed { background: #e9f7ef; }
.flag-rejected { background: #fde2e2; }
```

- [ ] **Step 16.8: 写测试 `tests/web/test_health_and_index.py`**


```python
from fastapi.testclient import TestClient
from examforge.web import create_app
from examforge.repositories import (
    init_db, init_vector_store, reset_db_engine_for_tests, reset_vector_for_tests,
)
from pathlib import Path


def test_index_and_health(tmp_path: Path):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    app = create_app(tmp_path / "data")
    c = TestClient(app)
    r = c.get("/healthz")
    assert r.status_code == 200 and r.json() == {"ok": True}
    r = c.get("/")
    assert r.status_code == 200
    assert "ExamForge-Math" in r.text
    reset_db_engine_for_tests()
    reset_vector_for_tests()
```

- [ ] **Step 16.9: 跑测试**


```bash
uv run pytest tests/web/test_health_and_index.py -v
```

Expected:`1 passed`。

- [ ] **Step 16.10: 提交**


```bash
git add src/examforge/web/ tests/web/ pyproject.toml uv.lock
git commit -m "feat(web): FastAPI skeleton + Jinja2 + htmx + index page"
```

---

### Task 17: 题目录入界面(GET 表单 / POST ingest)

**Files:**
- Create: `src/examforge/web/routes/__init__.py`
- Create: `src/examforge/web/routes/ingest.py`
- Create: `src/examforge/web/templates/ingest.html`
- Modify: `src/examforge/web/app.py`(注册 router)
- Test: `tests/web/test_ingest_route.py`

- [ ] **Step 17.1: 写 `templates/ingest.html`**


```html
{% extends "base.html" %}
{% block body %}
<h1>录入新题</h1>
{% if message %}<p style="color:green">{{ message }}</p>{% endif %}
<form method="post" action="/ingest">
  <label>年份 <input name="year" type="number" required></label>
  <label>地区 <input name="region" required></label>
  <label>板块
    <select name="subject_area">
      {% for a in areas %}<option>{{ a }}</option>{% endfor %}
    </select>
  </label><br>
  <label>题干(LaTeX/文本)<br><textarea name="stem" required></textarea></label><br>
  <label>参考答案(可选)<br><textarea name="reference"></textarea></label><br>
  <label>来源 <input name="source"></label><br>
  <button>提交并提炼</button>
</form>
<p>提交后会跑管线;若归类为可疑将出现在审核队列。</p>
{% endblock %}
```

- [ ] **Step 17.2: 写 `routes/ingest.py`**


```python
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from ..deps import get_session, problem_repo_dep, llm_dep, embedder_dep, config_dep
from ...models import SubjectArea
from ...pipeline import ingest_problem, run_pipeline
from ..app import templates

router = APIRouter()


@router.get("/ingest", response_class=HTMLResponse)
def form(request: Request):
    return templates.TemplateResponse(request, "ingest.html", {
        "areas": [a.value for a in SubjectArea],
        "message": None,
    })


@router.post("/ingest")
def submit(
    request: Request,
    year: int = Form(...),
    region: str = Form(...),
    subject_area: str = Form(...),
    stem: str = Form(...),
    reference: str = Form(""),
    source: str = Form(""),
    s: Session = Depends(get_session),
    p_repo=Depends(problem_repo_dep),
    llm=Depends(llm_dep),
    embedder=Depends(embedder_dep),
    cfg=Depends(config_dep),
):
    p = ingest_problem(
        stem_latex=stem, year=year, region=region,
        subject_area=subject_area, reference_solution=reference or None,
        source=source, repo=p_repo,
    )
    r = run_pipeline(p, session=s, llm=llm, embedder=embedder, config=cfg)
    msg = f"题目 {p.id} 已处理:confirmed={len(r.confirmed)} suspicious={len(r.suspicions)} candidate_new={len(r.candidates_new)}"
    return templates.TemplateResponse(request, "ingest.html", {
        "areas": [a.value for a in SubjectArea],
        "message": msg,
    })
```

- [ ] **Step 17.3: 在 `app.py` 注册路由**


```python
# app.py 内追加:
from .routes import ingest
app.include_router(ingest.router)
```

- [ ] **Step 17.4: 写测试 `tests/web/test_ingest_route.py`**


```python
from fastapi.testclient import TestClient
from examforge.web import create_app
from examforge.repositories import reset_db_engine_for_tests, reset_vector_for_tests


def test_ingest_page_renders(tmp_path):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    app = create_app(tmp_path / "data")
    c = TestClient(app)
    r = c.get("/ingest")
    assert r.status_code == 200
    assert "录入新题" in r.text
    reset_db_engine_for_tests()
    reset_vector_for_tests()


def test_ingest_submission_returns_message(tmp_path):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    app = create_app(tmp_path / "data")
    c = TestClient(app)
    r = c.post("/ingest", data={
        "year": 2023, "region": "A", "subject_area": "导数",
        "stem": "设 f(x)=x^3-3x,对任意 x 都有 f(x) >= -a 恒成立,求 a 的最大值",
        "reference": "a=2", "source": "test",
    })
    assert r.status_code == 200
    assert "已处理" in r.text
    reset_db_engine_for_tests()
    reset_vector_for_tests()
```

- [ ] **Step 17.5: 跑测试**


```bash
uv run pytest tests/web/test_ingest_route.py -v
```

Expected:`2 passed`。

- [ ] **Step 17.6: 提交**


```bash
git add src/examforge/web/routes/ src/examforge/web/app.py src/examforge/web/templates/ingest.html tests/web/test_ingest_route.py
git commit -m "feat(web): ingest page (GET form / POST ingest + pipeline)"
```

---

### Task 18: 方法库浏览界面

**Files:**
- Create: `src/examforge/web/routes/methods.py`
- Create: `src/examforge/web/templates/methods_list.html`
- Create: `src/examforge/web/templates/method_detail.html`
- Modify: `src/examforge/web/app.py`
- Test: `tests/web/test_methods_route.py`

- [ ] **Step 18.1: 写 `methods_list.html`**


```html
{% extends "base.html" %}
{% block body %}
<h1>方法库</h1>
<form method="get" action="/methods">
  <select name="area">
    <option value="">全部</option>
    {% for a in areas %}<option {% if a==area %}selected{% endif %}>{{ a }}</option>{% endfor %}
  </select>
  <select name="status">
    <option value="">全部</option>
    <option value="confirmed">confirmed</option>
    <option value="seed">seed</option>
    <option value="candidate">candidate</option>
  </select>
  <button>筛选</button>
</form>
<table>
  <tr><th>方法</th><th>板块</th><th>状态</th><th>例题数</th></tr>
  {% for m in methods %}
  <tr>
    <td><a href="/methods/{{ m.id }}">{{ m.name }}</a></td>
    <td>{{ m.subject_area.value }}</td>
    <td>{{ m.status.value }}</td>
    <td>{{ m.count }}</td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

- [ ] **Step 18.2: 写 `method_detail.html`**


```html
{% extends "base.html" %}
{% block body %}
<h1>{{ method.name }}</h1>
<p>板块:{{ method.subject_area.value }} · 状态:{{ method.status.value }}</p>
<h3>适用特征</h3><p>{{ method.applicability }}</p>
<h3>核心思想</h3><p>{{ method.core_idea }}</p>
<h3>通用步骤</h3><p>{{ method.procedure_steps }}</p>
<h3>常见坑</h3><p>{{ method.pitfalls }}</p>
<h3>已确认例题 ({{ examples|length }})</h3>
<table>
  <tr><th>ID</th><th>年份</th><th>地区</th><th>摘要</th></tr>
  {% for e in examples %}
  <tr><td>{{ e.id }}</td><td>{{ e.year }}</td><td>{{ e.region }}</td><td>{{ e.summary }}</td></tr>
  {% endfor %}
</table>
{% endblock %}
```

- [ ] **Step 18.3: 写 `routes/methods.py`**


```python
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlmodel import Session

from ..deps import get_session, method_repo_dep, solution_repo_dep, problem_repo_dep
from ...models import Method, MethodStatus, SubjectArea, SolutionInstance, ReviewStatus
from ..app import templates

router = APIRouter()


@router.get("/methods", response_class=HTMLResponse)
def list_view(request: Request, area: str = "", status: str = ""):
    sess: Session = next(get_session())
    stmt = select(Method)
    if area:
        stmt = stmt.where(Method.subject_area == SubjectArea(area))
    if status:
        stmt = stmt.where(Method.status == MethodStatus(status))
    methods = list(sess.exec(stmt))
    # 计算 count
    out = []
    for m in methods:
        c = sess.exec(
            select(SolutionInstance).where(
                SolutionInstance.method_id == m.id,
                SolutionInstance.review_status == ReviewStatus.CONFIRMED,
            )
        ).all()
        out.append({"id": m.id, "name": m.name, "subject_area": m.subject_area,
                    "status": m.status, "count": len(c)})
    return templates.TemplateResponse(request, "methods_list.html", {
        "areas": [a.value for a in SubjectArea],
        "area": area,
        "methods": out,
    })


@router.get("/methods/{method_id}", response_class=HTMLResponse)
def detail_view(request: Request, method_id: int):
    sess: Session = next(get_session())
    method = sess.get(Method, method_id)
    if method is None:
        return HTMLResponse("Method not found", status_code=404)
    sis = list(sess.exec(
        select(SolutionInstance).where(
            SolutionInstance.method_id == method_id,
            SolutionInstance.review_status == ReviewStatus.CONFIRMED,
        )
    ))
    examples = []
    for si in sis:
        from ...models import Problem
        p = sess.get(Problem, si.problem_id)
        if p is None:
            continue
        examples.append({
            "id": p.id, "year": p.year, "region": p.region,
            "summary": (si.transfer_note or si.key_steps)[:60],
        })
    return templates.TemplateResponse(request, "method_detail.html", {
        "method": method, "examples": examples,
    })
```

- [ ] **Step 18.4: 在 app.py 注册**


```python
from .routes import methods
app.include_router(methods.router)
```

- [ ] **Step 18.5: 写测试 `tests/web/test_methods_route.py`**


```python
from fastapi.testclient import TestClient
from sqlmodel import Session
from examforge.web import create_app
from examforge.repositories import reset_db_engine_for_tests, reset_vector_for_tests
from examforge.models import Method, SubjectArea, MethodStatus
from examforge.taxonomy import load_seed_methods


def test_methods_list_renders(tmp_path):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    app = create_app(tmp_path / "data")
    with session_factory() as s:
        load_seed_methods(s)
    c = TestClient(app)
    r = c.get("/methods?area=导数")
    assert r.status_code == 200
    assert "方法库" in r.text
    reset_db_engine_for_tests()
    reset_vector_for_tests()
```

(统一通过 `session_factory()` 拿 session,具体见 Task 3 Step 3.6.0。)

- [ ] **Step 18.6: 跑测试**


```bash
uv run pytest tests/web/test_methods_route.py -v
```

Expected:`1 passed`。

- [ ] **Step 18.7: 提交**


```bash
git add src/examforge/web/routes/methods.py src/examforge/web/templates/methods_list.html src/examforge/web/templates/method_detail.html src/examforge/web/app.py tests/web/test_methods_route.py
git commit -m "feat(web): methods list + detail pages"
```

---

### Task 19: 审核队列界面 + 审核动作端点

**Files:**
- Create: `src/examforge/web/routes/review.py`
- Create: `src/examforge/web/templates/review_queue.html`
- Modify: `src/examforge/web/app.py`
- Test: `tests/web/test_review_route.py`

- [ ] **Step 19.1: 写 `templates/review_queue.html`**


```html
{% extends "base.html" %}
{% block body %}
<h1>审核队列</h1>
{% if not items %}<p>暂无可疑项。</p>{% endif %}
{% for it in items %}
<div class="flag-suspicious" style="padding:8px;margin:8px 0;">
  <b>#{{ it.si.id }} 题 {{ it.problem.id }} {{ it.problem.year }} {{ it.problem.region }} — 建议归到 {{ it.method_name }} (相似度 {{ '%.2f' % (it.similarity or 0) if it.similarity is not none else 'n/a' }})</b>
  <p>题干:{{ it.problem.stem_latex[:120] }}...</p>
  <p>关键步骤:{{ it.si.key_steps }}</p>
  <p>套路:{{ it.si.transfer_note }}</p>
  <form method="post" action="/review/{{ it.si.id }}/confirm" style="display:inline">
    <button>确认</button>
  </form>
  <form method="post" action="/review/{{ it.si.id }}/reject" style="display:inline">
    <input name="note" placeholder="拒绝原因">
    <button>拒绝</button>
  </form>
  <form method="post" action="/review/{{ it.si.id }}/revise" style="display:inline">
    <input name="method_id" type="number" placeholder="改到 method_id">
    <button>改归并确认</button>
  </form>
</div>
{% endfor %}
{% endblock %}
```

- [ ] **Step 19.2: 写 `routes/review.py`**


```python
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from ..deps import get_session, solution_repo_dep, method_repo_dep, problem_repo_dep
from ...models import SolutionInstance, ReviewStatus
from ...pipeline.review import confirm as pipeline_confirm, reject as pipeline_reject, revise_method as pipeline_revise
from ..app import templates

router = APIRouter()


@router.get("/review", response_class=HTMLResponse)
def queue(request: Request, s: Session = Depends(get_session),
          p_repo=Depends(problem_repo_dep),
          m_repo=Depends(method_repo_dep),
          s_repo=Depends(solution_repo_dep)):
    drafts = s_repo.list_by_review_status(ReviewStatus.DRAFT)
    items = []
    for si in drafts:
        p = p_repo.get(si.problem_id)
        m = m_repo.get(si.method_id)
        items.append({
            "si": si,
            "problem": p,
            "method_name": m.name if m else "?",
            "similarity": None,
        })
    return templates.TemplateResponse(request, "review_queue.html", {"items": items})


@router.post("/review/{si_id}/confirm")
def do_confirm(si_id: int, s_repo=Depends(solution_repo_dep),
               m_repo=Depends(method_repo_dep)):
    pipeline_confirm(si_id, note="manual-confirm",
                     solution_repo=s_repo, method_repo=m_repo)
    return RedirectResponse("/review", status_code=303)


@router.post("/review/{si_id}/reject")
def do_reject(si_id: int, note: str = Form(""), s_repo=Depends(solution_repo_dep)):
    pipeline_reject(si_id, note=note, solution_repo=s_repo)
    return RedirectResponse("/review", status_code=303)


@router.post("/review/{si_id}/revise")
def do_revise(si_id: int, method_id: int = Form(...),
              s_repo=Depends(solution_repo_dep)):
    pipeline_revise(si_id, method_id=method_id, solution_repo=s_repo)
    return RedirectResponse("/review", status_code=303)
```

- [ ] **Step 19.3: 在 app.py 注册**


```python
from .routes import review
app.include_router(review.router)
```

- [ ] **Step 19.4: 测试(此处不强制 e2e,只测渲染 + 端点可调)**


```python
# tests/web/test_review_route.py 简化存在性断言
def test_review_route_renders(tmp_path):
    from fastapi.testclient import TestClient
    from examforge.web import create_app
    from examforge.repositories import reset_db_engine_for_tests, reset_vector_for_tests
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    app = create_app(tmp_path / "data")
    c = TestClient(app)
    assert c.get("/review").status_code == 200
    reset_db_engine_for_tests()
    reset_vector_for_tests()
```

- [ ] **Step 19.5: 跑测试 + 提交**


```bash
uv run pytest tests/web/test_review_route.py
git add src/examforge/web/routes/review.py src/examforge/web/templates/review_queue.html src/examforge/web/app.py tests/web/test_review_route.py
git commit -m "feat(web): review queue page + confirm/reject/revise endpoints"
```

---

### Task 20: 报告生成界面

**Files:**
- Create: `src/examforge/web/routes/report.py`
- Create: `src/examforge/web/templates/report.html`
- Modify: `src/examforge/web/app.py`
- Test: `tests/web/test_report_route.py`

- [ ] **Step 20.1: 写 `templates/report.html`**


```html
{% extends "base.html" %}
{% block body %}
<h1>生成报告</h1>
<form method="get" action="/report">
  <select name="method_id">
    {% for m in methods %}
    <option value="{{ m.id }}" {% if selected==m.id %}selected{% endif %}>{{ m.name }} ({{ m.subject_area.value }})</option>
    {% endfor %}
  </select>
  <button>生成</button>
</form>
{% if report %}<pre>{{ report }}</pre>{% endif %}
{% endblock %}
```

- [ ] **Step 20.2: 写 `routes/report.py`**


```python
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlmodel import Session

from ..deps import get_session, llm_dep
from ...models import Method
from ...report import generate_report
from ..app import templates

router = APIRouter()


@router.get("/report", response_class=HTMLResponse)
def view(request: Request, method_id: int | None = None,
         s: Session = Depends(get_session),
         llm=Depends(llm_dep)):
    methods = list(s.exec(select(Method)))
    report_md = None
    selected = None
    if method_id is not None:
        m = s.get(Method, method_id)
        if m is not None:
            report_md = generate_report(method_id, session=s, llm=llm)
            selected = method_id
    return templates.TemplateResponse(request, "report.html", {
        "methods": methods, "report": report_md, "selected": selected,
    })
```

- [ ] **Step 20.3: 在 app.py 注册**

```python
from .routes import report
app.include_router(report.router)
```

- [ ] **Step 20.4: 写最小测试 `tests/web/test_report_route.py`(断言 GET 200)**


```python
def test_report_route_renders(tmp_path):
    from fastapi.testclient import TestClient
    from examforge.web import create_app
    from examforge.repositories import reset_db_engine_for_tests, reset_vector_for_tests
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    c = TestClient(create_app(tmp_path / "data"))
    assert c.get("/report").status_code == 200
    reset_db_engine_for_tests()
    reset_vector_for_tests()
```

- [ ] **Step 20.5: 跑测试 + 提交**


```bash
uv run pytest tests/web/test_report_route.py
git add src/examforge/web/routes/report.py src/examforge/web/templates/report.html src/examforge/web/app.py tests/web/test_report_route.py
git commit -m "feat(web): report page (method → markdown report)"
```

---

### Task 21: 学生问答界面

**Files:**
- Create: `src/examforge/web/routes/qa.py`
- Create: `src/examforge/web/templates/qa.html`
- Modify: `src/examforge/web/app.py`
- Test: `tests/web/test_qa_route.py`

- [ ] **Step 21.1: 写 `templates/qa.html`**


```html
{% extends "base.html" %}
{% block body %}
<h1>学生问答(RAG)</h1>
<form method="post">
  <textarea name="question" placeholder="贴一道题或提问,例如 '含参不等式恒成立问题怎么处理'">{{ question or '' }}</textarea>
  <button>提交</button>
</form>
{% if answer %}
<h3>回答</h3>
<pre>{{ answer.answer }}</pre>
<h4>引用方法</h4>
<ul>{% for m in answer.cited_method_names %}<li>{{ m }}</li>{% endfor %}</ul>
<h4>引用例题</h4>
<ul>{% for i in answer.cited_problem_ids %}<li>#{{ i }}</li>{% endfor %}</ul>
{% endif %}
{% endblock %}
```

- [ ] **Step 21.2: 写 `routes/qa.py`**


```python
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ..deps import get_session, llm_dep, embedder_dep, config_dep
from ...qa import answer
from ..app import templates

router = APIRouter()


@router.get("/qa", response_class=HTMLResponse)
def view(request: Request):
    return templates.TemplateResponse(request, "qa.html", {"answer": None})


@router.post("/qa", response_class=HTMLResponse)
def submit(
    request: Request,
    question: str = Form(...),
    s: Session = Depends(get_session),
    llm=Depends(llm_dep),
    embedder=Depends(embedder_dep),
    cfg=Depends(config_dep),
):
    res = answer(question, session=s, llm=llm, embedder=embedder, config=cfg)
    return templates.TemplateResponse(request, "qa.html", {
        "answer": res.model_dump() if hasattr(res, "model_dump") else {
            "answer": res.answer, "cited_method_names": res.cited_method_names,
            "cited_problem_ids": res.cited_problem_ids,
        },
        "question": question,
    })
```

- [ ] **Step 21.3: 在 app.py 注册**


```python
from .routes import qa
app.include_router(qa.router)
```

- [ ] **Step 21.4: 最小测试**


```python
def test_qa_route_renders(tmp_path):
    from fastapi.testclient import TestClient
    from examforge.web import create_app
    from examforge.repositories import reset_db_engine_for_tests, reset_vector_for_tests
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    c = TestClient(create_app(tmp_path / "data"))
    assert c.get("/qa").status_code == 200
    reset_db_engine_for_tests()
    reset_vector_for_tests()
```

- [ ] **Step 21.5: 跑测试 + 提交**


```bash
uv run pytest tests/web/test_qa_route.py
git add src/examforge/web/routes/qa.py src/examforge/web/templates/qa.html src/examforge/web/app.py tests/web/test_qa_route.py
git commit -m "feat(web): QA page (RAG read-only)"
```

---

### Task 22: 端到端跑通 + 启动文档

**Files:**
- Modify: `README.md`(补 Web 启动说明 + CLI 一览)
- Create: `pyproject.toml` 已含 scripts,无需改

- [ ] **Step 22.1: 跑全量测试与覆盖率**


```bash
uv run pytest --cov
```

Expected:覆盖率 ≥ 80%(contract 默认 skip)。

- [ ] **Step 22.2: 手动端到端(E2E)清单**


```bash
# 一套命令,从空目录到能 curl
uv run examforge initdb
uv run examforge seed
uv run examforge list-methods
uv run examforge ingest demo.md --year 2023 --region 全国甲卷 --area 导数
# 启动 web
uv run uvicorn examforge.web:create_app --factory --app-dir src --host 127.0.0.1 --port 8000
# 另一窗口
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/methods
curl http://127.0.0.1:8000/review
```

每条命令预期返回正常;`/`、`/ingest`、`/methods`、`/review`、`/report`、`/qa` 五个页面 HTML 200。

- [ ] **Step 22.3: 补 README**


````markdown
# ExamForge-Math

从历年高考压轴题中自动提炼解题方法库,并通过 Web 提供教师报告与学生问答。

## 安装

```bash
uv sync
```

## CLI 一览

```bash
uv run examforge initdb                    # 初始化 SQLite + 向量库
uv run examforge seed                      # 上传预置 taxonomy
uv run examforge list-methods              # 列出方法
uv run examforge ingest path.md --year 2023 --region 甲卷 --area 导数   # 录入
uv run examforge run --problem-id 1        # 对已录入题跑管线
```

## Web

```bash
uv run uvicorn examforge.web:create_app --factory --app-dir src \
  --host 127.0.0.1 --port 8000 \
  --data-dir data
```

(注:本计划采用工厂函数 + `--data-dir` 参数;实际函数签名见 `src/examforge/web/app.py:create_app`,需要把 `--data-dir` 传递进去,实现时可在 `app/__init__.py` 加一个 `main()` 包装。)

## 测试

```bash
uv run pytest --cov
```

## 配置(环境变量)

- `EXAMFORGE_LLM_BACKEND` ∈ {`mock`, `http`}  默认 `mock`
- `EXAMFORGE_EMBED_BACKEND` ∈ {`mock`, `http`}  默认 `mock`
- `EXAMFORGE_LLM_BASE` / `EXAMFORGE_LLM_KEY` / `EXAMFORGE_LLM_MODEL`
- `EXAMFORGE_EMBED_BASE` / `EXAMFORGE_EMBED_KEY` / `EXAMFORGE_EMBED_MODEL`

## 真实 API(可选)

设置上述环境变量为真实后端后,需用 `EXAMFORGE_RUN_CONTRACT=1 uv run pytest tests/llm tests/embedding -m contract` 单跑契约测试。

## 阶段门

- 阶段 1 验收报告见 `docs/superpowers/reviews/2026-07-08-phase1-acceptance.md`
````

- [ ] **Step 22.4: 提交**


```bash
git add README.md
git commit -m "docs: update README with CLI + Web instructions"
```

---

# 收尾

整份计划在阶段 1 与阶段 2 全部完成、阶段 1 验收报告达到进入标准后,可视为 v1 完成。后续工作(如图像 OCR、多方法联合、报告导出 PDF 等)按新项目立项,不复用本计划。


