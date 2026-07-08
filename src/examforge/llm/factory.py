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


def get_llm(fail_open: bool = True):
    """获取 LLM 实例。

    fail_open=True(默认):当 http 配置完整但调用失败时,降级到 MockLLM 并返回;
    失败信息通过 stderr warning 输出,调用方在响应里也能看到。
    fail_open=False:严格模式,直接抛错。

    返回值带一个属性 `effective_backend` 告诉调用方"这次请求实际用的是 mock 还是 http"
    (用于在 UI 上显示)。
    """
    try:
        from ..config.settings import get_settings
        s = get_settings().llm
    except RuntimeError:
        s_llm = None
    else:
        s_llm = s

    if s_llm is None:
        # SettingsStore 未初始化
        inst = _fallback_llm()
        inst.effective_backend = "mock_fallback"
        return inst

    if s_llm.backend == "mock":
        inst = MockLLM()
        inst.effective_backend = "mock"
        return inst

    if s_llm.backend == "http":
        if not s_llm.api_key or not s_llm.base_url:
            warnings.warn(
                "LLM backend=http 但未配置 api_key 或 base_url,降级为 MockLLM",
                stacklevel=2,
            )
            inst = MockLLM()
            inst.effective_backend = "mock_fallback_no_key"
            return inst
        inst = HttpLLM(
            base_url=s_llm.base_url, api_key=s_llm.api_key,
            model=s_llm.model, timeout=s_llm.timeout,
        )
        inst.effective_backend = "http"
        return inst

    raise ValueError(f"未知 LLM backend: {s_llm.backend!r}")


def get_llm_safe():
    """为 ingest 端点准备:返回 (llm, original_backend) 元组。
    失败时降级 mock 并把信息反馈给前端。
    """
    inst = get_llm(fail_open=True)
    return inst, inst.effective_backend