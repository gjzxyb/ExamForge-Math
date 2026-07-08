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