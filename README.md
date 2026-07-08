# ExamForge-Math

从历年高考压轴题中自动提炼、沉淀结构化解题方法库,并通过 Web 提供教师报告与学生问答。

## 安装

```bash
uv sync
```

## CLI 一览

```bash
uv run examforge initdb                  # 初始化 SQLite + 向量库
uv run examforge seed                    # 上传预置 taxonomy(导数 + 圆锥曲线共 7 个方法)
uv run examforge list-methods            # 列出方法
uv run examforge list-methods --area 导数  # 按板块筛
uv run examforge ingest path.md --year 2023 --region 甲卷 --area 导数  # 录入并跑管线
uv run examforge run --problem-id 1      # 对已录入题单独跑管线
```

## Web 薄壳

```bash
uv run python -c "from examforge.web import create_app; create_app('data')"   # 仅作检查
uv run uvicorn examforge.web:create_app --factory --host 127.0.0.1 --port 8000 --app-dir src
```

启动后访问:

| 路径 | 作用 |
|---|---|
| `GET /` | 首页(统计) |
| `GET /healthz` | 健康检查 |
| `GET /ingest` | 题目录入表单 |
| `POST /ingest` | 提交并跑端到端管线 |
| `GET /methods` | 方法库列表(可按板块/状态筛) |
| `GET /methods/{id}` | 方法详情 + 已有例题 |
| `GET /review` | 审核队列 |
| `POST /review/{si_id}/confirm` | 确认一条可疑 SI |
| `POST /review/{si_id}/reject` | 拒绝一条可疑 SI |
| `POST /review/{si_id}/revise` | 改归并到另一 Method |
| `GET /report` | 教师报告(基于 confirmed 方法 + 例题) |
| `GET /qa` | 学生问答表单 |
| `POST /qa` | 提交问题,基于方法库 RAG 回答 |

## 测试

```bash
uv run pytest                # 跑测试
uv run pytest --cov          # 跑测试 + 覆盖率
uv run python tests/acceptance/run_eval.py   # 黄金集评估
```

## 配置(环境变量)

- `EXAMFORGE_LLM_BACKEND` ∈ {`mock`, `http`}  默认 `mock`
- `EXAMFORGE_EMBED_BACKEND` ∈ {`mock`, `http`}  默认 `mock`
- `EXAMFORGE_LLM_BASE` / `EXAMFORGE_LLM_KEY` / `EXAMFORGE_LLM_MODEL` (默认 DeepSeek)
- `EXAMFORGE_EMBED_BASE` / `EXAMFORGE_EMBED_KEY` / `EXAMFORGE_EMBED_MODEL`

## 真实 API(可选)

```bash
EXAMFORGE_LLM_BACKEND=http \
EXAMFORGE_LLM_KEY=sk-... \
EXAMFORGE_LLM_BASE=https://api.deepseek.com/v1 \
uv run python tests/acceptance/run_eval.py
```

契约测试:

```bash
EXAMFORGE_RUN_CONTRACT=1 uv run pytest -m contract
```

## 阶段门

阶段 1 验收报告见 `docs/superpowers/reviews/2026-07-08-phase1-acceptance.md`。
设计 spec 见 `docs/superpowers/specs/2026-07-08-examforge-math-design.md`。
实现计划见 `docs/superpowers/plans/2026-07-08-examforge-math.md`。

## 结构

```
src/examforge/
├── core/
│   ├── models/         # Problem / Method / SolutionInstance + 3 枚举
│   ├── repositories/   # SQLite + Chroma
│   ├── embedding/      # Embedder protocol + Mock + Http
│   ├── llm/            # LLM protocol + Mock + Http + pydantic schemas + prompts
│   ├── taxonomy/       # 预置方法种子(导数 4 + 圆锥曲线 3)
│   ├── pipeline/       # Ingest / Extract / Classify / Review / Commit / Orchestrator
│   ├── report/         # 应用 A · Reporter
│   ├── qa/             # 应用 B · QA (RAG)
│   └── config/         # PipelineConfig
├── cli/                # Typer CLI
└── web/                # FastAPI 薄壳 + Jinja2 + htmx
```

## 后续

- 接入真实 DeepSeek 做正式黄金集评估
- 图像入口(腾讯云/阿里云公式识别 API)—— 已留 `Problem.image_ref` 字段
- 多方法联合(一题多方法关联表)
- 报告导出 PDF
