"""黄金集评估脚本。

用法:
    uv run python tests/acceptance/run_eval.py

输出 docs/superpowers/reviews/2026-07-08-phase1-eval.json,含每题管线结果。
人工对比后写入 docs/superpowers/reviews/2026-07-08-phase1-acceptance.md。
"""

import json
import sys
import argparse
from pathlib import Path
from sqlalchemy import select

from examforge.repositories import (
    init_db, init_vector_store, reset_db_engine_for_tests,
    reset_vector_for_tests, problem_repo, get_session,
)
from examforge.embedding import MockEmbedder
from examforge.llm import MockLLM
from examforge.config import PipelineConfig
from examforge.models import SubjectArea, Problem, Method
from examforge.taxonomy import load_seed_methods
from examforge.pipeline import run_pipeline
from examforge.repositories import make_fingerprint


def load_golden(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path, default=Path("data/eval"))
    p.add_argument("--golden", type=Path,
                   default=Path("tests/acceptance/golden_set.json"))
    p.add_argument("--use-mock-llm", action="store_true", default=True)
    args = p.parse_args()

    reset_db_engine_for_tests()
    reset_vector_for_tests()
    init_db(args.data_dir)
    init_vector_store(args.data_dir / "chroma")

    s = get_session()
    # 清空(防止历史残留)
    for m in s.exec(select(Method)):
        s.delete(m)
    s.commit()
    load_seed_methods(s)

    items = load_golden(args.golden)
    rows = []
    for it in items:
        problem = problem_repo().upsert_by_fingerprint(Problem(
            year=it["year"], region=it["region"],
            subject_area=SubjectArea(it["subject_area"]),
            stem_latex=it["stem_latex"],
            reference_solution=it.get("reference_solution"),
            content_fingerprint=make_fingerprint(
                it["stem_latex"], it["year"], it["region"],
            ),
        ))
        r = run_pipeline(problem, session=s,
                         llm=MockLLM(),
                         embedder=MockEmbedder(),
                         config=PipelineConfig())
        rows.append({
            "id": it["id"],
            "year": it["year"],
            "subject_area": it["subject_area"],
            "expected_methods": it["expected_methods"],
            "expected_classification": it["expected_classification"],
            "confirmed": r.confirmed,
            "suspicions": r.suspicions,
            "candidates_new": r.candidates_new,
        })

    out_path = Path("docs/superpowers/reviews/2026-07-08-phase1-eval.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"wrote {out_path} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())