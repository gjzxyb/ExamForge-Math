"""根据配置选择 embedder。"""

import os
from .types import Embedder
from .mock_embedder import MockEmbedder
from .http_embedder import HttpEmbedder

_BACKEND = os.environ.get("EXAMFORGE_EMBED_BACKEND", "mock")


def get_embedder(backend: str | None = None) -> Embedder:
    """默认 mock(测试默认路径);生产通过 EXAMFORGE_EMBED_BACKEND=http 切换。"""
    b = backend or _BACKEND
    if b == "mock":
        return MockEmbedder()
    if b == "http":
        return HttpEmbedder()
    raise ValueError(f"未知 embedding 后端: {b}")