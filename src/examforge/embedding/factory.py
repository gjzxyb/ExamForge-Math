"""根据 Settings 选择 embedder,行为同 get_llm。

- 显式传 backend 时用之(向后兼容老测试)
- 否则读 Settings;未初始化则回退到环境变量
"""

import os
import warnings
from .types import Embedder
from .mock_embedder import MockEmbedder
from .http_embedder import HttpEmbedder


def _fallback_embedder() -> Embedder:
    backend = os.environ.get("EXAMFORGE_EMBED_BACKEND", "mock")
    if backend == "mock":
        return MockEmbedder()
    if backend == "http":
        if not os.environ.get("EXAMFORGE_EMBED_KEY", ""):
            warnings.warn(
                "Embedder backend=http 但未配置 api_key,降级为 MockEmbedder",
                stacklevel=2,
            )
            return MockEmbedder()
        return HttpEmbedder()
    raise ValueError(f"未知 embedding backend: {backend}")


def get_embedder(backend: str | None = None) -> Embedder:
    """若显式传 backend,忽略 Settings(向后兼容老测试)。
    否则从 Settings 读最新值;未初始化则回退环境变量。
    """
    if backend is not None:
        if backend == "mock":
            return MockEmbedder()
        if backend == "http":
            return HttpEmbedder()
        raise ValueError(f"未知 embedding backend: {backend}")

    try:
        from ..config.settings import get_settings
        s = get_settings().embedder
    except RuntimeError:
        return _fallback_embedder()

    if s.backend == "mock":
        return MockEmbedder()
    if s.backend == "http":
        if not s.api_key or not s.base_url:
            warnings.warn(
                "Embedder backend=http 但未配置 api_key 或 base_url,降级为 MockEmbedder",
                stacklevel=2,
            )
            return MockEmbedder()
        return HttpEmbedder(
            base_url=s.base_url, api_key=s.api_key,
            model=s.model, dim=s.dim, timeout=s.timeout,
        )
    raise ValueError(f"未知 Embedder backend: {s.backend!r}")