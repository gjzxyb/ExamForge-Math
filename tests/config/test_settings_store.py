"""Settings 存储 + Web 路由测试。"""

import json
import pytest
from pathlib import Path

from examforge.config.settings import (
    Settings, SettingsStore, LLMSettings, EmbedderSettings, OCRSettings,
    init_settings_store, get_settings, get_settings_store,
)
from examforge.repositories import (
    reset_db_engine_for_tests, reset_vector_for_tests,
)


@pytest.fixture
def fresh_store(tmp_path):
    """每个测试一份新 store,避免全局单例串扰。"""
    # 重置模块单例
    import examforge.config.settings as mod
    mod._store = None
    yield tmp_path
    mod._store = None


def test_settings_from_env_overrides(fresh_store, monkeypatch):
    monkeypatch.setenv("EXAMFORGE_LLM_KEY", "sk-test-from-env")
    monkeypatch.setenv("EXAMFORGE_EMBED_DIM", "768")
    monkeypatch.setenv("EXAMFORGE_OCR_PROVIDER", "tencent")

    store = SettingsStore(fresh_store)
    s = store.get()
    assert s.llm.api_key == "sk-test-from-env"
    assert s.embedder.dim == 768
    assert s.ocr.provider == "tencent"


def test_settings_persists_to_disk_and_reloads(fresh_store):
    store1 = SettingsStore(fresh_store)
    store1.update(llm={"api_key": "sk-persisted", "model": "m-1"})
    # 模拟重启
    store2 = SettingsStore(fresh_store)
    s = store2.get()
    assert s.llm.api_key == "sk-persisted"
    assert s.llm.model == "m-1"


def test_settings_partial_update_keeps_other_fields(fresh_store):
    store = SettingsStore(fresh_store)
    store.update(llm={"api_key": "k1", "base_url": "u1", "model": "m1", "backend": "http", "timeout": 10.0})
    # 只改 backend
    store.update(llm={"backend": "mock"})
    s = store.get()
    assert s.llm.backend == "mock"
    assert s.llm.api_key == "k1"   # 保留
    assert s.llm.base_url == "u1"  # 保留
    assert s.llm.model == "m1"     # 保留
    assert s.llm.timeout == 10.0   # 保留


def test_settings_corrupt_disk_falls_back_to_env(fresh_store, monkeypatch):
    (fresh_store).mkdir(parents=True, exist_ok=True)
    (fresh_store / "settings.json").write_text("not json{", encoding="utf-8")
    monkeypatch.setenv("EXAMFORGE_LLM_KEY", "sk-fallback")
    s = SettingsStore(fresh_store).get()
    assert s.llm.api_key == "sk-fallback"