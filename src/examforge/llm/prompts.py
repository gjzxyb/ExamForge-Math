"""Prompt 模板。集中放这里便于后续 A/B 优化。"""


EXTRACT_SYSTEM = """高中数学解题方法提炼助手。输入:题目+候选方法清单。
任务:识别使用的方法、关键步骤、套路、适用特征,输出置信度。
约束:
- 严格 JSON 格式
- 优先使用候选清单中的方法名,无合适时自拟(confidence<0.6)
"""


def apply_model_control(system_prompt: str) -> str:
    """把设置页中的全局模型约束与 Skill 说明注入 system prompt。

    该函数只追加用户在"设置 → 模型约束与 Skills"中保存的 Markdown，
    不改变原有任务 JSON schema 约束；若 SettingsStore 未初始化则保持原 prompt。
    """
    try:
        from ..config.settings import get_settings
        control = get_settings().model_control
    except Exception:
        return system_prompt

    blocks = [system_prompt.rstrip()]
    if control.enabled and control.agent_md.strip():
        blocks.append(
            "## 全局模型约束 / AGENT.md\n"
            "以下内容优先作为行为边界、质量要求和禁止事项执行；"
            "但不得覆盖本次任务要求的严格 JSON 输出格式。\n"
            f"{control.agent_md.strip()}"
        )
    if control.skills_enabled and control.skills_md.strip():
        blocks.append(
            "## 可用 Skills\n"
            "下面是本系统启用的技能说明。你应先判断任务是否匹配某个 Skill；"
            "匹配时按 Skill 的流程和约束组织推理与输出；不匹配时忽略。\n"
            f"{control.skills_md.strip()}"
        )
    return "\n\n".join(blocks)


def extract_user_prompt(stem: str, reference: str | None,
                        hint_names: list[str], area: str) -> str:
    hint = ", ".join(hint_names) if hint_names else "(无)"
    ref = reference or "(无)"
    return f"""板块:{area} | 候选:{hint}

题干:{stem}

参考答案:{ref}

JSON 字段:summary(思路综述), methods[method_name,subject_area,key_steps,transfer_note,applicability,key_theorem,secondary_theorems,confidence], overall_confidence
注:key_theorem 空填"", secondary_theorems 空填[]
"""


REPORT_SYSTEM = """数学教研报告撰写助手,整理方法知识为专题报告。"""


def report_user_prompt(name: str, app: str, ci: str, proc: str,
                       pit: str, examples: list[dict]) -> str:
    lines = "\n".join(
        f"- {e.get('year', '?')} {e.get('region', '?')}: {e.get('summary', '')[:60]}"
        for e in examples
    )
    return f"""方法:{name} | 适用:{app} | 核心:{ci}
步骤:{proc} | 坑:{pit}
例题({len(examples)}道):{lines}

JSON字段:intro,core_idea,procedure,applicability,pitfalls,examples_markdown
"""


QA_SYSTEM = """解题方法学徒。仅依据给定方法知识+例题作答,不凭直觉。知识不足时明确说明,不编造。"""


def qa_user_prompt(question: str, method_doc: str, examples: list[dict]) -> str:
    lines = "\n".join(
        f"- (id={e.get('id', '?')}) {e.get('summary', '')[:80]}"
        for e in examples
    )
    return f"""问题:{question}

方法知识:{method_doc}

例题:{lines}

JSON:answer,cited_method_names,cited_problem_ids
"""

ANSWER_SYSTEM = """高中数学答案生成助手。根据题干+参考材料+搜索摘要生成答案与推导。
要求:
- answer:最终答案(可含 LaTeX),简洁明确
- 数学公式:行内 \\( ... \\),独立行 $$ ... $$
- analysis_steps:Markdown 分节(## 审题、## 转化、## 计算、## 验证、## 易错点、## 搜索参考),≤3500字
- 每段简短,不重复题干,接近上限时优先闭合 JSON
- 搜索参考仅作核验,不照抄
- 信息不足时给最可能答案,说明假设并降低 confidence
- 严格 JSON,无其它文本
"""


def answer_user_prompt(
    stem: str,
    subject_area: str,
    reference: str | None = None,
    web_context: str | None = None,
) -> str:
    ref = reference or "(无)"
    web = web_context or "(无)"
    return f"""模块:{subject_area}

题干:{stem}

参考:{ref}

搜索:{web}

JSON:answer(含LaTeX),analysis_steps(≤3500字Markdown),confidence(0-1)
"""
