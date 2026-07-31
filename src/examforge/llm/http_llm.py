"""HTTP LLM 客户端(默认走 DeepSeek 兼容协议)。

错误处理:最多 retry 2 次(共 3 次调用),仍失败抛 `LLMHttpError`,
外层 catch 后可降级到 MockLLM 或把错误回传前端。
"""

import json
import os
from typing import Any
import httpx
from pydantic import TypeAdapter, ValidationError
from .schemas import ExtractedSolution, ReportedSections, QAResult, GeneratedAnswer


DEFAULT_BASE = os.environ.get("EXAMFORGE_LLM_BASE", "https://api.deepseek.com/v1")
DEFAULT_KEY = os.environ.get("EXAMFORGE_LLM_KEY", "")
DEFAULT_MODEL = os.environ.get("EXAMFORGE_LLM_MODEL", "deepseek-chat")
MIN_HTTP_LLM_TIMEOUT = float(os.environ.get("EXAMFORGE_LLM_MIN_TIMEOUT", "180"))
HTTP_LLM_CONNECT_TIMEOUT = float(os.environ.get("EXAMFORGE_LLM_CONNECT_TIMEOUT", "15"))
HTTP_LLM_WRITE_TIMEOUT = float(os.environ.get("EXAMFORGE_LLM_WRITE_TIMEOUT", "30"))
MAX_JSON_OUTPUT_TOKENS = int(os.environ.get("EXAMFORGE_LLM_MAX_JSON_TOKENS", "8192"))
ANSWER_JSON_OUTPUT_TOKENS = int(os.environ.get("EXAMFORGE_LLM_ANSWER_TOKENS", "8192"))


def effective_llm_timeout(timeout: float | int | str | None) -> float:
    """真实 LLM 长 prompt 请求的最小超时。

    DeepSeek/OpenAI 兼容接口在生成详细解析、报告或 RAG 回答时常超过
    60 秒；这里统一把 http 后端请求级 read timeout 提升到至少 180 秒，
    避免用户设置页仍保存旧的 60 秒导致正式生成反复超时。
    """
    try:
        value = float(timeout) if timeout is not None else MIN_HTTP_LLM_TIMEOUT
    except (TypeError, ValueError):
        value = MIN_HTTP_LLM_TIMEOUT
    return max(value, MIN_HTTP_LLM_TIMEOUT)


def _normalize_llm_json_payload(data: Any) -> Any:
    """兼容真实模型偶发的 schema 小偏差。

    例如 ExtractedSolution.methods[].secondary_theorems 要求数组,但模型常返回
    空字符串 "" 或用分号/换行拼成字符串。这里在 Pydantic 校验前递归归一化,
    避免前端 ingest 因可恢复格式问题降级为 mock。
    """
    if isinstance(data, dict):
        normalized = {k: _normalize_llm_json_payload(v) for k, v in data.items()}
        if "secondary_theorems" in normalized:
            value = normalized["secondary_theorems"]
            if value is None or value == "":
                normalized["secondary_theorems"] = []
            elif isinstance(value, str):
                parts: list[str] = []
                for line in value.replace("\r", "\n").split("\n"):
                    for part in line.replace("；", ";").replace("，", ",").split(";"):
                        for sub in part.split(","):
                            item = sub.strip()
                            if item:
                                parts.append(item)
                normalized["secondary_theorems"] = parts
        return normalized
    if isinstance(data, list):
        return [_normalize_llm_json_payload(item) for item in data]
    return data


def _validate_llm_json(content: str, schema_model: type) -> Any:
    """解析 LLM JSON，并在校验前做可恢复字段归一化。"""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # 保留原始错误路径,让 Pydantic 报 JSON 解析错误。
        return TypeAdapter(schema_model).validate_json(content)
    return TypeAdapter(schema_model).validate_python(_normalize_llm_json_payload(data))


def _json_validation_message(exc: ValidationError, *, finish_reason: str | None) -> str:
    """把模型截断导致的 Pydantic JSON 错误转换为可重试、可读的错误。"""
    detail = str(exc)
    truncated = finish_reason == "length" or any(marker in detail for marker in (
        "EOF while parsing", "EOF while parsing a string", "json_eof",
    ))
    if truncated:
        return "LLM 输出达到长度上限，返回的 JSON 被截断；系统将增大输出上限后重试"
    return f"LLM 返回的 JSON 格式无效: {detail[:400]}"

class LLMHttpError(RuntimeError):
    """HTTP LLM 调不通时抛此异常(替代裸 tenacity.RetryError,语义清晰)。"""
    def __init__(self, message: str, *, status_code: int | None = None,
                 body: str | None = None, request_url: str | None = None,
                 timeout_seconds: float | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.request_url = request_url
        self.timeout_seconds = timeout_seconds
        self.body = (body or "")[:500]  # 截断避免泄露太多

    def as_user_message(self) -> str:
        """给前端显示的用户友好消息:含 URL、状态码、底层异常与 body 摘要。"""
        parts = [f"URL: {self.request_url}"] if self.request_url else []
        raw_message = str(self)
        if raw_message and not raw_message.startswith("HTTP "):
            parts.append(f"错误: {raw_message}")
        if self.status_code:
            code_meaning = {
                401: "认证失败(API key 无效或缺失)",
                402: "余额不足或需要付费",
                403: "禁止访问(可能 IP 不在白名单或 region 受限)",
                404: "路径错(检查 base_url 末尾是否要加 /v1)",
                429: "限流(请求太频繁)",
                500: "服务端内部错误",
                502: "网关错误(可能是 base_url 配错)",
                503: "服务不可用",
            }.get(self.status_code, f"HTTP {self.status_code}")
            parts.append(code_meaning)
        if self.body:
            # 截掉可能的 HTML 错误页
            body_clean = self.body.replace("\n", " ")[:200]
            parts.append(f"响应: {body_clean}")
        msg = " · ".join(parts) or raw_message
        lower = msg.lower()
        if "timed out" in lower or "timeout" in lower or "超时" in msg:
            if self.timeout_seconds:
                msg += f" · 本次请求已使用 {int(self.timeout_seconds)} 秒超时。"
            msg += " · 系统已把真实 LLM 请求级超时提升到至少 180 秒；若仍超时,请检查 DeepSeek 服务状态/网络代理,或在设置中继续增大到 240-300 秒。"
        return msg


class HttpLLM:
    def __init__(self, base_url: str = DEFAULT_BASE, api_key: str = DEFAULT_KEY,
                 model: str = DEFAULT_MODEL, timeout: float = 60.0,
                 max_retries: int = 2) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        try:
            self._configured_timeout = float(timeout)
        except (TypeError, ValueError):
            self._configured_timeout = MIN_HTTP_LLM_TIMEOUT
        self._timeout = effective_llm_timeout(timeout)
        self._client = httpx.Client(timeout=httpx.Timeout(
            connect=min(HTTP_LLM_CONNECT_TIMEOUT, self._timeout),
            read=self._timeout,
            write=min(HTTP_LLM_WRITE_TIMEOUT, self._timeout),
            pool=min(HTTP_LLM_CONNECT_TIMEOUT, self._timeout),
        ))
        self._max_retries = max_retries

    @property
    def timeout(self) -> float:
        return self._timeout

    @property
    def configured_timeout(self) -> float:
        return self._configured_timeout

    def _chat_json(
        self,
        *,
        system: str,
        user: str,
        schema_model: type,
        max_tokens: int | None = None,
        retry_user_suffix: str = "",
    ) -> Any:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        last_err: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                request_max_tokens = None
                if max_tokens:
                    request_max_tokens = min(
                        max_tokens * (2 ** attempt),
                        MAX_JSON_OUTPUT_TOKENS,
                    )
                resp = self._client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system},
                            {
                                "role": "user",
                                "content": user + (retry_user_suffix if attempt else ""),
                            },
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2,
                        **({"max_tokens": request_max_tokens} if request_max_tokens else {}),
                    },
                )
                # 4xx/5xx 不抛,手工 raise 以便带 status
                if resp.status_code >= 400:
                    raise LLMHttpError(
                        f"HTTP {resp.status_code} from LLM",
                        status_code=resp.status_code,
                        body=resp.text,
                        request_url=str(resp.request.url),
                    )
                choice = resp.json()["choices"][0]
                content = choice["message"]["content"]
                try:
                    return _validate_llm_json(content, schema_model)
                except ValidationError as exc:
                    last_err = LLMHttpError(
                        _json_validation_message(
                            exc,
                            finish_reason=choice.get("finish_reason"),
                        ),
                        request_url=str(resp.request.url),
                    )
                    if attempt < self._max_retries:
                        import time
                        time.sleep(2 ** attempt)
                        continue
                    raise last_err
            except LLMHttpError as e:
                last_err = e
                # 4xx(认证、参数错)立即失败,不再 retry
                if e.status_code and 400 <= e.status_code < 500:
                    raise
            except (httpx.RequestError, KeyError, IndexError) as e:
                last_err = e
                # 连接错也带上 URL。Timeout 单独说明,否则 str(ReadTimeout) 为空时前端只剩 URL。
                if isinstance(e, httpx.RequestError) and e.request:
                    if isinstance(e, httpx.TimeoutException):
                        detail = str(e) or f"请求超过 {self._timeout} 秒未返回"
                        message = f"LLM 请求超时: {detail}"
                    else:
                        detail = str(e) or e.__class__.__name__
                        message = f"无法连接 LLM: {detail}"
                    last_err = LLMHttpError(
                        message,
                        request_url=str(e.request.url),
                        timeout_seconds=self._timeout,
                    )
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
        from .prompts import EXTRACT_SYSTEM, apply_model_control, extract_user_prompt
        sys = apply_model_control(EXTRACT_SYSTEM)
        user = extract_user_prompt(stem_latex, reference_solution, taxonomy_hint, subject_area)
        return self._chat_json(system=sys, user=user, schema_model=ExtractedSolution, max_tokens=2048)

    def generate_answer(self, *, stem_latex, subject_area, reference_solution=None, web_context=None):
        from .prompts import ANSWER_SYSTEM, apply_model_control, answer_user_prompt
        sys = apply_model_control(ANSWER_SYSTEM)
        user = answer_user_prompt(stem_latex, subject_area, reference_solution, web_context)
        return self._chat_json(
            system=sys,
            user=user,
            schema_model=GeneratedAnswer,
            max_tokens=ANSWER_JSON_OUTPUT_TOKENS,
            retry_user_suffix=(
                "\n\n上一次回答因过长被截断。请重新独立生成完整 JSON；"
                "将 analysis_steps 压缩到 3500 个中文字符以内，保留关键推导、"
                "结论与验证，禁止重复题干，务必闭合所有字符串、公式与 JSON。"
            ),
        )

    def render_report(self, *, method_name, applicability, core_idea,
                      procedure, pitfalls, examples):
        from .prompts import REPORT_SYSTEM, apply_model_control, report_user_prompt
        sys = apply_model_control(REPORT_SYSTEM)
        user = report_user_prompt(method_name, applicability, core_idea,
                                  procedure, pitfalls, examples)
        return self._chat_json(system=sys, user=user, schema_model=ReportedSections, max_tokens=4096)

    def answer_question(self, *, question, method_doc, examples):
        from .prompts import QA_SYSTEM, apply_model_control, qa_user_prompt
        sys = apply_model_control(QA_SYSTEM)
        user = qa_user_prompt(question, method_doc, examples)
        return self._chat_json(system=sys, user=user, schema_model=QAResult, max_tokens=2048)
