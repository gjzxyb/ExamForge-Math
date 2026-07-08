"""Settings Web 端到端测试。"""

import json
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from examforge.web import create_app
from examforge.repositories import (
    reset_db_engine_for_tests, reset_vector_for_tests,
)


@pytest.fixture
def client(tmp_path):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    # 重置 settings store 单例
    import examforge.config.settings as mod
    mod._store = None
    app = create_app(tmp_path / "data")
    yield TestClient(app)
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    mod._store = None


def test_settings_page_renders(client):
    r = client.get("/settings")
    assert r.status_code == 200
    assert "语言模型" in r.text
    assert "Embedder" in r.text
    assert "公式识别" in r.text


def test_settings_save_llm_persists(client):
    r = client.post("/settings/llm", data={
        "backend": "http",
        "base_url": "https://api.test/v1",
        "api_key": "sk-xyz",
        "model": "test-model",
        "timeout": "30.0",
    }, follow_redirects=False)
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # 读盘验证
    settings_path = client.app.state.data_dir / "settings.json"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["llm"]["api_key"] == "sk-xyz"
    assert data["llm"]["model"] == "test-model"


def test_settings_save_ocr_persists_without_calling_api(client):
    """OCR 配置项不接实现,但能保存。"""
    r = client.post("/settings/ocr", data={
        "provider": "tencent",
        "access_key_id": "ak",
        "access_key_secret": "sk",
        "region": "ap-shanghai",
        "endpoint": "ocr.tencentcloudapi.com",
    }, follow_redirects=False)
    assert r.status_code == 200
    assert r.json()["ok"] is True

    settings_path = client.app.state.data_dir / "settings.json"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["ocr"]["provider"] == "tencent"
    assert data["ocr"]["region"] == "ap-shanghai"


def test_settings_test_llm_with_mock_succeeds(client):
    r = client.post("/settings/test-llm")
    assert r.status_code == 200
    body = r.json()
    # 默认 mock,应该 OK
    assert body["ok"] is True
    assert body["backend"] == "mock"


def test_settings_test_embedder_with_mock_succeeds(client):
    r = client.post("/settings/test-embedder")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["backend"] == "mock"
    assert body["dim"] == 64  # MockEmbedder dim


def test_settings_test_llm_with_bad_http_fails_gracefully(client):
    """http 后端但 base_url 不可达 → 返 {ok:false, error},不 5xx。"""
    client.post("/settings/llm", data={
        "backend": "http",
        "base_url": "http://127.0.0.1:1",  # 一定不通
        "api_key": "k",
        "model": "m",
        "timeout": "1.0",
    })
    r = client.post("/settings/test-llm")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "error" in body


def test_changing_llm_backend_takes_effect(client):
    """改完 LLM backend=mock → 下次 /ingest 不应报错。"""
    client.post("/settings/llm", data={
        "backend": "mock", "base_url": "", "api_key": "",
        "model": "deepseek-chat", "timeout": "60.0",
    })
    r = client.post("/ingest", data={
        "year": 2023, "region": "A", "subject_area": "导数",
        "stem": "若 a>0 任意实数 x f(x) >= -a 恒成立 求 a 的最大值",
        "reference": "a=2", "source": "settings test",
    })
    assert r.status_code == 200
    assert "已处理" in r.text