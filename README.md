# ExamForge-Math

从历年高考压轴题中提炼、沉淀解题方法库。

## 开发

```bash
uv sync               # 安装依赖
uv run pytest         # 跑测试
uv run pytest --cov   # 跑测试 + 覆盖率
```

## 结构

- `src/examforge/core/` — 核心引擎(models / repositories / LLM / embedding / pipeline)
- `src/examforge/web/` — FastAPI 薄壳(阶段 2)
- `src/examforge/taxonomy/` — 预置方法种子
- `tests/` — TDD 测试

## 阶段门

阶段 1(核心引擎)完成并通过黄金集验证后,才能进入阶段 2(Web)。
