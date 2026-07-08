"""HTTP LLM 客户端(默认走 DeepSeek 兼容协议)。

错误处理:最多 retry 2 次(共 3 次调用),仍失败抛 `LLMHttpError`,
外层 catch 后可降级到 MockLLM 或把错误回传前端。
"""

import os
from typing import Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
from pydantic import TypeAdapter
from .schemas import ExtractedSolution, ReportedSections, QAResult


DEFAULT_BASE = os.environ.get("EXAMFORGE_LLM_BASE", "https://api.deepseek.com/v1")
DEFAULT_KEY = os.environ.get("EXAMFORGE_LLM_KEY", "")
DEFAULT_MODEL = os.environ.get("EXAMFORGE_LLM_MODEL", "deepseek-chat")


class LLMHttpError(RuntimeError):
    """HTTP LLM 调不通时抛此异常(替代裸 tenacity.RetryError,语义清晰)。"""
    def __init__(self, message: str, *, status_code: int | None = None,
                 body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = (body or "")[:500]  # 截断避免泄露太多


class HttpLLM:
    def __init__(self, base_url: str = DEFAULT_BASE, api_key: str = DEFAULT_KEY,
                 model: str = DEFAULT_MODEL, timeout: float = 60.0,
                 max_retries: int = 2) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)
        self._max_retries = max_retries

    @property
    def timeout(self) -> float:
        return self._timeout

    def _chat_json(self, *, system: str, user: str, schema_model: type) -> Any:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        last_err: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "response_format": {"type": "json_object"},
                    },
                )
                # 4xx/5xx 不抛,手工 raise 以便带 status
                if resp.status_code >= 400:
                    raise LLMHttpError(
                        f"HTTP {resp.status_code} from LLM",
                        status_code=resp.status_code,
                        body=resp.text,
                    )
                content = resp.json()["choices"][0]["message"]["content"]
                return TypeAdapter(schema_model).validate_json(content)
            except LLMHttpError as e:
                last_err = e
                # 4xx(认证、参数错)立即失败,不再 retry
                if e.status_code and 400 <= e.status_code < 500:
                    raise
            except (httpx.RequestError, KeyError, IndexError) as e:
                last_err = e
                if attempt < self._max_retries:
                    import time
                    time.sleep(2 ** attempt)
                    continue
        # 全部 retry 耗尽
        if isinstance(last_err, LLMHttpError):
            raise last_err
        raise LLMHttpError(f"LLM 调用失败: {last_err}")

    def extract_solution(self, *, stem_latex, reference_solution,
                         taxonomy_hint, subject_area):
        from .prompts import EXTRACT_SYSTEM, extract_user_prompt
        sys = EXTRACT_SYSTEM
        user = extract_user_prompt(stem_latex, reference_solution, taxonomy_hint, subject_area)
        return self._chat_json(system=sys, user=user, schema_model=ExtractedSolution)

    def render_report(self, *, method_name, applicability, core_idea,
                      procedure, pitfalls, examples):
        from .prompts import REPORT_SYSTEM, report_user_prompt
        sys = REPORT_SYSTEM
        user = report_user_prompt(method_name, applicability, core_idea,
                                  procedure, pitfalls, examples)
        return self._chat_json(system=sys, user=user, schema_model=ReportedSections)

    def answer_question(self, *, question, method_doc, examples):
        from .prompts import QA_SYSTEM, qa_user_prompt
        sys = QA_SYSTEM
        user = qa_user_prompt(question, method_doc, examples)
        return self._chat_json(system=sys, user=user, schema_model=QAResult)