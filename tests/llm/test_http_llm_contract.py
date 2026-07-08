import os
import pytest

pytestmark = pytest.mark.contract


@pytest.mark.skipif(
    not os.environ.get("EXAMFORGE_RUN_CONTRACT"),
    reason="set EXAMFORGE_RUN_CONTRACT=1 to run",
)
def test_http_llm_returns_valid_schema():
    from examforge.llm import HttpLLM, ExtractedSolution
    llm = HttpLLM()
    out = llm.extract_solution(
        stem_latex="设 f(x)=x^3-3x, 若对任意实数 x, f(x) >= -a 恒成立, 求 a 的最大值。",
        reference_solution="a=2",
        taxonomy_hint=["分离参数法"],
        subject_area="导数",
    )
    ExtractedSolution.model_validate(out.model_dump())  # 二次确认