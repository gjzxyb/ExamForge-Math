"""Prompt 模板。集中放这里便于后续 A/B 优化。"""


EXTRACT_SYSTEM = """你是高中数学解题方法提炼助手。
输入是一道题(含可选参考答案)与候选方法清单(来自现有 taxonomy)。
任务:判断这道题用了哪些方法、关键步骤、可迁移套路、适用特征,并自报置信度。
约束:
- 输出必须是严格 JSON,不含其它文本。
- 方法名优先使用候选清单里的名字,除非确无合适者,自拟新名并在 confidence<0.6。
"""


def extract_user_prompt(stem: str, reference: str | None,
                        hint_names: list[str], area: str) -> str:
    hint = ", ".join(hint_names) if hint_names else "(无候选)"
    ref = reference or "(无参考答案)"
    return f"""板块:{area}
候选方法清单:{hint}

题干(LaTeX/文本):
{stem}

参考答案:{ref}

请输出 JSON,字段:
- summary: 整道题的一句话思路综述
- methods: 列表,每项含 method_name/subject_area/key_steps/transfer_note/applicability/confidence
- overall_confidence: 整道题整体置信度
"""


REPORT_SYSTEM = """你是数学教研报告撰写助手,负责把方法知识整理为可读专题报告。
"""


def report_user_prompt(name: str, app: str, ci: str, proc: str,
                       pit: str, examples: list[dict]) -> str:
    lines = "\n".join(
        f"- {e.get('year', '?')} {e.get('region', '?')}: {e.get('summary', '')[:60]}"
        for e in examples
    )
    return f"""方法名:{name}
适用特征:{app}
核心思想:{ci}
通用步骤:{proc}
常见坑:{pit}
例题({len(examples)} 道):
{lines}

请输出 JSON,字段:intro/core_idea/procedure/applicability/pitfalls/examples_markdown(对应例题表)。
"""


QA_SYSTEM = """你是解题方法学徒。请仅依据“给定方法知识 + 给定例题 ”作答,不要凭直觉。
如所给知识不足,明确说明缺失,不要编造。
"""


def qa_user_prompt(question: str, method_doc: str, examples: list[dict]) -> str:
    lines = "\n".join(
        f"- (id={e.get('id', '?')}) {e.get('summary', '')[:80]}"
        for e in examples
    )
    return f"""问题:{question}

已知方法知识:
{method_doc}

已知例题:
{lines}

输出 JSON:answer/cited_method_names/cited_problem_ids。
"""