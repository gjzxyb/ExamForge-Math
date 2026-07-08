import os
from .mock_llm import MockLLM
from .http_llm import HttpLLM

_BACKEND = os.environ.get("EXAMFORGE_LLM_BACKEND", "mock")


def get_llm(backend: str | None = None):
    b = backend or _BACKEND
    if b == "mock":
        return MockLLM()
    if b == "http":
        return HttpLLM()
    raise ValueError(f"未知 LLM 后端: {b}")