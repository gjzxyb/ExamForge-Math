from typer.testing import CliRunner
from examforge.cli import app

runner = CliRunner()


def test_help_succeeds():
    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0
    assert "ExamForge" in res.output