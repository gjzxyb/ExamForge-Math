from pathlib import Path
from fastapi.testclient import TestClient
from examforge.web import create_app
from examforge.repositories import (
    reset_db_engine_for_tests, reset_vector_for_tests,
)


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