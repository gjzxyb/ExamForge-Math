"""HTTP LLM 客户端(默认走 DeepSeek 兼容协议)。"""

import os
from typing import Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from pydantic import TypeAdapter
from .schemas import ExtractedSolution, ReportedSections, QAResult


DEFAULT_BASE = os.environ.get("EXAMFORGE_LLM_BASE", "https://api.deepseek.com/v1")
DEFAULT_KEY = os.environ.get("EXAMFORGE_LLM_KEY", "")
DEFAULT_MODEL = os.environ.get("EXAMFORGE_LLM_MODEL", "deepseek-chat")


class HttpLLM:
    def __init__(self, base_url: str = DEFAULT_BASE, api_key: str = DEFAULT_KEY,
                 model: str = DEFAULT_MODEL, timeout: float = 60.0) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self._client = httpx.Client(timeout=timeout)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20))
    def _chat_json(self, *, system: str, user: str, schema_model: type) -> Any:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        # 多数兼容协议:response_format=json_schema 仅部分后端支持;这里使用
        # 强制 prompt 输出 JSON + 服务端 json_object 模式兜底。
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
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        # 用 pydantic v2 TypeAdapter 验证
        return TypeAdapter(schema_model).validate_json(content)

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