from examforge.llm import MockLLM, get_llm


def test_mock_extract_returns_valid_schema():
    llm = MockLLM()
    out = llm.extract_solution(
        stem_latex="若 a>0, 任意 x, 都有 f(x)>=a 恒成立",
        reference_solution="略",
        taxonomy_hint=["分离参数法", "切线放缩"],
        subject_area="导数",
    )
    assert out.summary
    assert out.methods
    assert 0.0 <= out.overall_confidence <= 1.0


def test_factory_default_returns_mock(monkeypatch):
    monkeypatch.delenv("EXAMFORGE_LLM_BACKEND", raising=False)
    assert get_llm().__class__.__name__ == "MockLLM"

def test_mock_generate_answer_returns_generated_answer():
    llm = MockLLM()
    out = llm.generate_answer(
        stem_latex="若对任意 x, x^2+a>=0 恒成立, 求 a",
        subject_area="导数",
        reference_solution=None,
    )
    assert out.answer
    assert "自动生成占位答案" in out.answer
    assert out.analysis_steps
    assert 0.0 <= out.confidence <= 1.0
