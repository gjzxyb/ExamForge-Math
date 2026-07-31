"""HttpLLM 错误处理 + 用户友好消息。"""

import pytest
from examforge.llm.http_llm import LLMHttpError


def test_llm_http_error_carries_status_and_url():
    e = LLMHttpError("boom", status_code=401, body="Invalid API key",
                     request_url="https://api.deepseek.com/v1/chat/completions")
    assert e.status_code == 401
    assert e.request_url.endswith("/chat/completions")
    msg = e.as_user_message()
    assert "URL:" in msg
    assert "认证失败" in msg  # 401 状态码被翻译
    assert "Invalid API key" in msg


def test_llm_http_error_unknown_status_still_renders():
    e = LLMHttpError("boom", status_code=418, body="I am a teapot",
                     request_url="http://x/")
    msg = e.as_user_message()
    assert "HTTP 418" in msg  # 未知状态码走 fallback 文本
    assert "I am a teapot" in msg


def test_llm_http_error_truncates_long_body():
    long_body = "x" * 5000
    e = LLMHttpError("boom", status_code=500, body=long_body,
                     request_url="http://x/")
    # 内部 body 截到 500
    assert len(e.body) == 500
    # 用户消息再截到 200
    msg = e.as_user_message()
    assert len(msg) < 1000


def test_status_code_meanings_cover_common_codes():
    """关键状态码有用户友好解释。"""
    cases = {
        401: "认证失败",
        402: "余额不足",
        403: "禁止访问",
        404: "路径错",
        429: "限流",
        500: "服务端内部错误",
        502: "网关错误",
        503: "服务不可用",
    }
    for code, expected_phrase in cases.items():
        e = LLMHttpError("x", status_code=code, body="b", request_url="http://x/")
        assert expected_phrase in e.as_user_message(), f"code {code} not translated"


def test_validate_llm_json_normalizes_secondary_theorems_empty_string():
    from examforge.llm.http_llm import _validate_llm_json
    from examforge.llm.schemas import ExtractedSolution

    content = '{"summary":"思路","methods":[{"method_name":"分离参数法","subject_area":"导数","key_steps":"步骤","transfer_note":"套路","applicability":"条件","key_theorem":"","secondary_theorems":"","confidence":0.8}],"overall_confidence":0.8}'
    out = _validate_llm_json(content, ExtractedSolution)
    assert out.methods[0].secondary_theorems == []


def test_validate_llm_json_normalizes_key_steps_array_from_llm():
    from examforge.llm.http_llm import _validate_llm_json
    from examforge.llm.schemas import ExtractedSolution

    content = '{"summary":["思路一","思路二"],"methods":[{"method_name":"定义法","subject_area":"数与式","key_steps":["识别为加法运算","根据加法定义得出和 2"],"transfer_note":"套路","applicability":"条件","key_theorem":"","secondary_theorems":"","confidence":0.8}],"overall_confidence":0.8}'
    out = _validate_llm_json(content, ExtractedSolution)
    assert out.summary == "思路一\n思路二"
    assert out.methods[0].key_steps == "识别为加法运算\n根据加法定义得出和 2"


def test_validate_llm_json_defaults_missing_method_confidence():
    from examforge.llm.http_llm import _validate_llm_json
    from examforge.llm.schemas import ExtractedSolution

    content = '{"summary":"思路","methods":[{"method_name":"定义法","subject_area":"数与式","key_steps":["将两个1相加","根据加法定义得到2。"],"transfer_note":"套路","applicability":"条件","key_theorem":"","secondary_theorems":""}]}'
    out = _validate_llm_json(content, ExtractedSolution)
    assert out.methods[0].key_steps == "将两个1相加\n根据加法定义得到2。"
    assert out.methods[0].confidence == 0.6
    assert out.overall_confidence == 0.6


def test_http_llm_chat_json_accepts_real_model_empty_string_secondary_theorems():
    from examforge.llm.http_llm import HttpLLM
    from examforge.llm.schemas import ExtractedSolution

    class FakeRequest:
        url = "https://llm.test/v1/chat/completions"

    class FakeResponse:
        status_code = 200
        text = "ok"
        request = FakeRequest()

        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": '{"summary":"思路","methods":[{"method_name":"分离参数法","subject_area":"导数","key_steps":"步骤","transfer_note":"套路","applicability":"条件","key_theorem":"","secondary_theorems":"","confidence":0.8}],"overall_confidence":0.8}'
                    }
                }]
            }

    class FakeClient:
        def post(self, *args, **kwargs):
            return FakeResponse()

    llm = HttpLLM(base_url="https://llm.test/v1", api_key="k", max_retries=0)
    llm._client = FakeClient()
    out = llm._chat_json(system="s", user="u", schema_model=ExtractedSolution)
    assert out.methods[0].secondary_theorems == []


def test_http_llm_retries_truncated_generated_answer_with_more_tokens(monkeypatch):
    from examforge.llm.http_llm import HttpLLM
    from examforge.llm.schemas import GeneratedAnswer

    monkeypatch.setattr("time.sleep", lambda _: None)
    requests = []

    class FakeRequest:
        url = "https://llm.test/v1/chat/completions"

    class FakeResponse:
        status_code = 200
        text = "ok"
        request = FakeRequest()

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    class FakeClient:
        def post(self, *args, **kwargs):
            requests.append(kwargs["json"])
            if len(requests) == 1:
                return FakeResponse({"choices": [{
                    "finish_reason": "length",
                    "message": {"content": '{"answer":"$a=2$","analysis_steps":"未完成'},
                }]})
            return FakeResponse({"choices": [{
                "finish_reason": "stop",
                "message": {"content": '{"answer":"$a=2$","analysis_steps":"完整步骤","confidence":0.8}'},
            }]})

    llm = HttpLLM(base_url="https://llm.test/v1", api_key="k", max_retries=2)
    llm._client = FakeClient()
    out = llm._chat_json(
        system="s", user="u", schema_model=GeneratedAnswer, max_tokens=4096,
    )

    assert out.answer == "$a=2$"
    assert out.analysis_steps == "完整步骤"
    assert [request["max_tokens"] for request in requests] == [4096, 8192]


def test_generate_answer_starts_with_full_output_budget_and_shortens_retry(monkeypatch):
    from examforge.llm.http_llm import HttpLLM

    monkeypatch.setattr("time.sleep", lambda _: None)
    requests = []

    class FakeRequest:
        url = "https://llm.test/v1/chat/completions"

    class FakeResponse:
        status_code = 200
        text = "ok"
        request = FakeRequest()

        def __init__(self, complete):
            self.complete = complete

        def json(self):
            if not self.complete:
                return {"choices": [{
                    "finish_reason": "length",
                    "message": {"content": '{"answer":"2","analysis_steps":"过长'},
                }]}
            return {"choices": [{
                "finish_reason": "stop",
                "message": {"content": '{"answer":"2","analysis_steps":"精简完整步骤","confidence":0.8}'},
            }]}

    class FakeClient:
        def post(self, *args, **kwargs):
            requests.append(kwargs["json"])
            return FakeResponse(complete=len(requests) > 1)

    llm = HttpLLM(base_url="https://llm.test/v1", api_key="k", max_retries=2)
    llm._client = FakeClient()
    result = llm.generate_answer(stem_latex="1+1", subject_area="数与式")

    assert result.analysis_steps == "精简完整步骤"
    assert requests[0]["max_tokens"] == 8192
    assert requests[1]["max_tokens"] == 8192
    assert "上一次回答因过长被截断" not in requests[0]["messages"][1]["content"]
    assert "上一次回答因过长被截断" in requests[1]["messages"][1]["content"]
    assert "3500" in requests[1]["messages"][1]["content"]


def test_http_llm_reports_truncated_json_as_friendly_error(monkeypatch):
    from examforge.llm.http_llm import HttpLLM
    from examforge.llm.schemas import GeneratedAnswer

    monkeypatch.setattr("time.sleep", lambda _: None)

    class FakeRequest:
        url = "https://llm.test/v1/chat/completions"

    class FakeResponse:
        status_code = 200
        text = "ok"
        request = FakeRequest()

        def json(self):
            return {"choices": [{
                "finish_reason": "length",
                "message": {"content": '{"answer":"$a=2$","analysis_steps":"未完成'},
            }]}

    class FakeClient:
        def post(self, *args, **kwargs):
            return FakeResponse()

    llm = HttpLLM(base_url="https://llm.test/v1", api_key="k", max_retries=1)
    llm._client = FakeClient()
    with pytest.raises(LLMHttpError) as caught:
        llm._chat_json(
            system="s", user="u", schema_model=GeneratedAnswer, max_tokens=4096,
        )

    assert "JSON 被截断" in caught.value.as_user_message()
    assert "ValidationError" not in caught.value.as_user_message()


def test_llm_http_error_includes_request_error_message_without_status():
    e = LLMHttpError(
        "LLM 请求超时: 请求超过 3 秒未返回",
        request_url="https://api.deepseek.com/v1/chat/completions",
    )
    msg = e.as_user_message()
    assert "URL:" in msg
    assert "LLM 请求超时" in msg
    assert "超时" in msg


def test_http_llm_uses_minimum_timeout_for_long_real_calls():
    from examforge.llm.http_llm import HttpLLM

    llm = HttpLLM(base_url="https://llm.test/v1", api_key="k", timeout=30, max_retries=0)
    assert llm.configured_timeout == 30
    assert llm.timeout >= 180


def test_llm_http_timeout_message_mentions_effective_timeout():
    e = LLMHttpError(
        "LLM 请求超时: The read operation timed out",
        request_url="https://api.deepseek.com/v1/chat/completions",
        timeout_seconds=180,
    )
    msg = e.as_user_message()
    assert "本次请求已使用 180 秒超时" in msg
    assert "240-300" in msg
