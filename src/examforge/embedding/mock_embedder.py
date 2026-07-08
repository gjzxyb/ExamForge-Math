"""用于测试的 deterministic 嵌入器(基于 SHA256 派生 64 维向量)。"""

import hashlib
from typing import Iterable


class MockEmbedder:
    DIM = 64

    def dim(self) -> int:
        return self.DIM

    def _vec(self, text: str) -> list[float]:
        raw = hashlib.sha256(text.encode()).digest()
        # 扩展到 64 维:复用 32 字节两次,归一化
        buf = (raw * 2)[: self.DIM]
        out = [b / 255.0 for b in buf]
        # L2 normalize
        s = sum(x * x for x in out) ** 0.5 or 1.0
        return [x / s for x in out]

    def embed(self, text: str) -> list[float]:
        return self._vec(text)

    def embed_batch(self, texts: Iterable[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]