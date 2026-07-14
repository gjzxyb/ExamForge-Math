import pytest
from pydantic import ValidationError
from examforge.llm import ExtractedSolution, ProposedMethodUse, GeneratedAnswer


def test_extracted_solution_validates_valid_payload():
    data = {
        "summary": "思路",
        "methods": [{
            "method_name": "分离参数法",
            "subject_area": "导数",
            "key_steps": "步骤",
            "transfer_note": "套路",
            "applicability": "适用特征",
            "confidence": 0.7,
        }],
        "overall_confidence": 0.7,
    }
    obj = ExtractedSolution.model_validate(data)
    assert obj.methods[0].method_name == "分离参数法"


def test_extracted_solution_rejects_bad_confidence():
    with pytest.raises(ValidationError):
        ProposedMethodUse(
            method_name="x", subject_area="导数",
            key_steps="", transfer_note="", applicability="",
            confidence=1.5,
        )


def test_extracted_solution_accepts_secondary_theorems_empty_string_from_llm():
    data = {
        "summary": "思路",
        "methods": [{
            "method_name": "分离参数法",
            "subject_area": "导数",
            "key_steps": "步骤",
            "transfer_note": "套路",
            "applicability": "适用特征",
            "key_theorem": "",
            "secondary_theorems": "",
            "confidence": 0.7,
        }],
        "overall_confidence": 0.7,
    }
    obj = ExtractedSolution.model_validate(data)
    assert obj.methods[0].secondary_theorems == []


def test_extracted_solution_splits_secondary_theorems_string_from_llm():
    data = {
        "summary": "思路",
        "methods": [{
            "method_name": "定理法",
            "subject_area": "导数",
            "key_steps": "步骤",
            "transfer_note": "套路",
            "applicability": "适用特征",
            "secondary_theorems": "罗尔定理；介值定理\n闭区间最值定理",
            "confidence": 0.8,
        }],
        "overall_confidence": 0.8,
    }
    obj = ExtractedSolution.model_validate(data)
    assert obj.methods[0].secondary_theorems == ["罗尔定理", "介值定理", "闭区间最值定理"]


def test_extracted_solution_normalizes_llm_text_arrays():
    data = {
        "summary": ["先判断运算类型", "再按定义计算"],
        "methods": [{
            "method_name": ["加法定义", "直接计算"],
            "subject_area": "数与式",
            "key_steps": ["识别为加法运算", "根据加法定义得出和 2"],
            "transfer_note": ["遇到同类基础运算", "先还原定义再计算"],
            "applicability": ["题干直接给出运算", "目标为最终结果"],
            "key_theorem": {"name": "加法定义", "note": "同号数相加取相同符号"},
            "secondary_theorems": "",
            "confidence": 0.8,
        }],
        "overall_confidence": 0.8,
    }
    obj = ExtractedSolution.model_validate(data)
    assert obj.summary == "先判断运算类型\n再按定义计算"
    assert obj.methods[0].method_name == "加法定义\n直接计算"
    assert obj.methods[0].key_steps == "识别为加法运算\n根据加法定义得出和 2"
    assert "加法定义" in obj.methods[0].key_theorem


def test_generated_answer_normalizes_step_arrays_from_llm():
    obj = GeneratedAnswer.model_validate({
        "answer": ["$2$"],
        "analysis_steps": ["识别为加法运算", "计算得到 2"],
        "confidence": 0.8,
    })
    assert obj.answer == "$2$"
    assert obj.analysis_steps == "识别为加法运算\n计算得到 2"


def test_generated_answer_validates_confidence():
    obj = GeneratedAnswer.model_validate({
        "answer": "$a=2$",
        "analysis_steps": "求最值得到答案",
        "confidence": 0.8,
    })
    assert obj.answer == "$a=2$"
    with pytest.raises(ValidationError):
        GeneratedAnswer(answer="x", confidence=1.2)


def test_generated_answer_rejects_blank_answer():
    with pytest.raises(ValidationError):
        GeneratedAnswer(answer="   ", confidence=0.7)
