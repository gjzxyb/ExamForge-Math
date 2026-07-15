from examforge.llm.prompts import extract_user_prompt, report_user_prompt, qa_user_prompt, answer_user_prompt


def test_extract_prompt_includes_hint_names():
    p = extract_user_prompt("stem", "ref", ["分离参数法", "切线放缩"], "导数")
    assert "分离参数法" in p and "切线放缩" in p
    assert "导数" in p


def test_extract_prompt_handles_no_hint():
    p = extract_user_prompt("stem", None, [], "导数")
    assert "(无候选)" in p


def test_report_prompt_lists_examples():
    p = report_user_prompt("X", "A", "I", "P", "Pt",
                           [{"year": 2023, "region": "甲", "summary": "题目摘要"}])
    assert "2023" in p and "甲" in p


def test_qa_prompt_keeps_questions_separate():
    p = qa_user_prompt("Q?", "DOC", [{"id": 1, "summary": "x"}])
    assert "Q?" in p and "DOC" in p

def test_answer_prompt_requests_json_fields():
    p = answer_user_prompt("stem", "导数", None)
    assert "answer" in p
    assert "analysis_steps" in p
    assert "confidence" in p
    assert "导数" in p


def test_answer_prompt_includes_detailed_requirement_and_web_context():
    p = answer_user_prompt(
        "stem", "导数", None,
        "[1] 某解析\n摘要: 用分离参数求最值\nURL: https://example.com",
    )
    assert "全网搜索参考" in p
    assert "某解析" in p
    assert "详细推导步骤" in p
    assert "Markdown" in p
    assert "标准 LaTeX" in p or "$$" in p
    assert "审题" in p and "验证" in p
