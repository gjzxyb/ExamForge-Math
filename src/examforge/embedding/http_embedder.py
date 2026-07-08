"""基于 httpx 的 embedding 客户端。默认走国内 embedding 兼容协议。

实际生产可替换为 DeepSeek / 自托管 BGE / 通义千问 等;此实现作为可配置接入点。
"""

import os
from typing import Iterable
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

DEFAULT_BASE = os.environ.get("EXAMFORGE_EMBED_BASE", "https://api.example.com")
DEFAULT_KEY = os.environ.get("EXAMFORGE_EMBED_KEY", "")
DEFAULT_MODEL = os.environ.get("EXAMFORGE_EMBED_MODEL", "text-embedding-3-small")
DEFAULT_DIM = int(os.environ.get("EXAMFORGE_EMBED_DIM", "1024"))


class HttpEmbedder:
    def __init__(self, base_url: str = DEFAULT_BASE, api_key: str = DEFAULT_KEY,
                 model: str = DEFAULT_MODEL, dim: int = DEFAULT_DIM,
                 timeout: float = 30.0) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self._dim = dim
        self._client = httpx.Client(timeout=timeout)

    def dim(self) -> int:
        return self._dim

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def _call(self, inputs: list[str]) -> list[list[float]]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        resp = self._client.post(
            f"{self.base_url}/embeddings",
            headers=headers,
            json={"model": self.model, "input": inputs},
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data["data"]]

    def embed(self, text: str) -> list[float]:
        return self._call([text])[0]

    def embed_batch(self, texts: Iterable[str]) -> list[list[float]]:
        items = list(texts)
        if not items:
            return []
        return self._call(items)