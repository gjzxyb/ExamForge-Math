"""Embedding 抽象接口。"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...
    def embed_batch(self, texts) -> list[list[float]]: ...
    def dim(self) -> int: ...