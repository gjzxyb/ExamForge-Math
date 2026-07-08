import pytest
from pydantic import ValidationError
from examforge.llm import ExtractedSolution, ProposedMethodUse


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