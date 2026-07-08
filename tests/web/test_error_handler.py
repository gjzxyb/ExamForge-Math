"""全局异常处理测试。"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from examforge.web import create_app
from examforge.repositories import (
    reset_db_engine_for_tests, reset_vector_for_tests,
)


@pytest.fixture
def client(tmp_path):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    import examforge.config.settings as mod
    mod._store = None
    app = create_app(tmp_path / "data")
    # raise_server_exceptions=False 让 TestClient 不把 server 异常抛回 Python,
    # 而是像真实 uvicorn 那样走 exception_handler 返 500 响应。
    yield TestClient(app, raise_server_exceptions=False)
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    mod._store = None


def test_500_returns_html_with_traceback(client):
    """注入一个会抛异常的路由来验证全局 handler 真的工作。"""
    @client.app.get("/_test_boom")
    def boom():
        raise RuntimeError("deliberate failure for test abc123")

    r = client.get("/_test_boom", headers={"Accept": "text/html"})
    assert r.status_code == 500
    assert "Internal Server Error" in r.text
    assert "RuntimeError" in r.text
    assert "deliberate failure for test abc123" in r.text
    assert "Traceback" in r.text


def test_500_returns_json_for_json_accept(client):
    @client.app.get("/_test_boom2")
    def boom2():
        raise ValueError("nope xyz789")

    r = client.get("/_test_boom2", headers={"Accept": "application/json"})
    assert r.status_code == 500
    body = r.json()
    assert body["error"] == "ValueError"
    assert "nope xyz789" in body["message"]
    assert "Traceback" in body["traceback"]


def test_normal_routes_still_work(client):
    r = client.get("/healthz")
    assert r.status_code == 200