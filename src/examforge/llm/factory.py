"""根据 Settings 选择 LLM,每次调用读最新配置。

行为:
- backend=mock → MockLLM
- backend=http 且 base_url + api_key 都有 → HttpLLM
- backend=http 但缺 key → 降级到 MockLLM(并 warning),不会让请求因鉴权失败
- SettingsStore 未初始化时回退到环境变量(向后兼容老测试/CLI)
"""

import os
import warnings
from .mock_llm import MockLLM
from .http_llm import HttpLLM


def _fallback_llm():
    """Settings 未初始化时的兜底:用环境变量。"""
    backend = os.environ.get("EXAMFORGE_LLM_BACKEND", "mock")
    if backend == "mock":
        return MockLLM()
    if backend == "http":
        base = os.environ.get("EXAMFORGE_LLM_BASE", "https://api.deepseek.com/v1")
        key = os.environ.get("EXAMFORGE_LLM_KEY", "")
        model = os.environ.get("EXAMFORGE_LLM_MODEL", "deepseek-chat")
        if not key:
            warnings.warn(
                "LLM backend=http 但未配置 api_key,降级为 MockLLM",
                stacklevel=2,
            )
            return MockLLM()
        return HttpLLM(base_url=base, api_key=key, model=model)
    raise ValueError(f"未知 LLM backend: {backend!r}")


def get_llm():
    try:
        from ..config.settings import get_settings
        s = get_settings().llm
    except RuntimeError:
        return _fallback_llm()
    if s.backend == "mock":
        return MockLLM()
    if s.backend == "http":
        if not s.api_key or not s.base_url:
            warnings.warn(
                "LLM backend=http 但未配置 api_key 或 base_url,降级为 MockLLM",
                stacklevel=2,
            )
            return MockLLM()
        return HttpLLM(
            base_url=s.base_url, api_key=s.api_key,
            model=s.model, timeout=s.timeout,
        )
    raise ValueError(f"未知 LLM backend: {s.backend!r}")