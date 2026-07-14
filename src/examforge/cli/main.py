"""ExamForge CLI。"""

import json
from pathlib import Path
import typer
from rich.console import Console

from .bootstrap import bootstrap, get_session_for_cli

app = typer.Typer(help="ExamForge CLI")
console = Console()


@app.command()
def initdb(data_dir: Path = Path("data")) -> None:
    """初始化数据库与向量库。"""
    bootstrap(data_dir)
    console.print(f"[green]Initialized at {data_dir}/[/]")


@app.command()
def seed(data_dir: Path = Path("data")) -> None:
    """上传预置 taxonomy 种子方法。"""
    bootstrap(data_dir)
    from ..taxonomy import load_seed_methods
    s = get_session_for_cli(data_dir)
    ms = load_seed_methods(s)
    console.print(f"[green]Loaded {len(ms)} seed methods[/]")


@app.command()
def ingest(
    filepath: Path,
    data_dir: Path = Path("data"),
    year: int = typer.Option(...),
    region: str = typer.Option(...),
    area: str = typer.Option(...),
    ref: Path = typer.Option(None, help="参考答案/解析文件路径"),
    answer: str = typer.Option("", help="标准答案/最终结果"),
    sub_knowledge: str = typer.Option("", help="子知识点"),
    problem_type_tags: str = typer.Option("", help="题型标签,逗号分隔"),
    image_ref: str = typer.Option("", help="题图路径或 URL"),
    source: str = "",
) -> None:
    """录入一道题(从纯文本文件)。"""
    bootstrap(data_dir)
    s = get_session_for_cli(data_dir)
    from ..repositories import ProblemRepo
    from ..pipeline import ingest_problem
    stem = filepath.read_text(encoding="utf-8")
    ref_txt = ref.read_text(encoding="utf-8") if ref else None
    repo = ProblemRepo(s)
    p = ingest_problem(
        stem_latex=stem, year=year, region=region,
        subject_area=area, reference_solution=ref_txt,
        answer=answer or None,
        official_analysis_steps=ref_txt,
        sub_knowledge=sub_knowledge,
        problem_type_tags=problem_type_tags,
        image_ref=image_ref or None,
        source=source, repo=repo,
    )
    console.print(f"[green]Problem {p.id} fingerprint={p.content_fingerprint}[/]")


@app.command()
def run(problem_id: int, data_dir: Path = Path("data")) -> None:
    """对已录入题跑端到端管线。"""
    bootstrap(data_dir)
    from ..repositories import ProblemRepo
    from ..llm import get_llm
    from ..embedding import get_embedder
    from ..config import get_config
    from ..pipeline import run_pipeline
    from ..models import Problem

    s = get_session_for_cli(data_dir)
    llm = get_llm()
    embedder = get_embedder()
    cfg = get_config()
    p = ProblemRepo(s).get(problem_id)
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
    bootstrap(data_dir)
    from sqlalchemy import select
    from ..models import Method, SubjectArea
    s = get_session_for_cli(data_dir)
    stmt = select(Method)
    if area:
        stmt = stmt.where(Method.subject_area == SubjectArea(area))
    rows = list(s.exec(stmt))
    for m in rows:
        console.print(f"- [{m.status.value}] {m.name} ({m.subject_area.value})")


@app.command()
def serve(
    data_dir: Path = Path("data"),
    host: str = typer.Option(
        "0.0.0.0",
        help="监听地址；0.0.0.0 表示允许通过本机局域网 IP + 端口访问。",
    ),
    port: int = typer.Option(8000, help="监听端口。"),
    reload: bool = typer.Option(False, help="开发模式自动重载。"),
) -> None:
    """启动 Web 服务。默认监听 0.0.0.0,支持局域网 IP 访问。"""
    import uvicorn
    from ..web import create_app

    app_obj = create_app(data_dir)
    console.print(f"[green]ExamForge Web listening on {host}:{port}[/]")
    if host == "0.0.0.0":
        console.print("[yellow]可在本机用 http://127.0.0.1:%s 访问；局域网设备请用 http://<本机IP>:%s 访问。[/]" % (port, port))
    uvicorn.run(app_obj, host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()