"""Prompt 模板。集中放这里便于后续 A/B 优化。"""


EXTRACT_SYSTEM = """你是高中数学解题方法提炼助手。
输入是一道题(含可选参考答案)与候选方法清单(来自现有 taxonomy)。
任务:判断这道题用了哪些方法、关键步骤、可迁移套路、适用特征,并自报置信度。
约束:
- 输出必须是严格 JSON,不含其它文本。
- 方法名优先使用候选清单里的名字,除非确无合适者,自拟新名并在 confidence<0.6。
"""


def apply_model_control(system_prompt: str) -> str:
    """把设置页中的全局模型约束与 Skill 说明注入 system prompt。

    该函数只追加用户在“设置 → 模型约束与 Skills”中保存的 Markdown，
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
    hint = ", ".join(hint_names) if hint_names else "(无候选)"
    ref = reference or "(无参考答案)"
    return f"""板块:{area}
候选方法清单:{hint}

题干(LaTeX/文本):
{stem}

参考答案:{ref}

请输出 JSON,字段:
- summary: 整道题的一句话思路综述
- methods: 列表,每项含 method_name/subject_area/key_steps/transfer_note/applicability/key_theorem/secondary_theorems/confidence
- overall_confidence: 整道题整体置信度
- 若题中存在比常规方法更关键的定理、推论或二级定理,必须写入 key_theorem / secondary_theorems。
- key_theorem 没有则填空字符串 ""；secondary_theorems 必须始终是数组,没有则填 []，不要填空字符串。
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

ANSWER_SYSTEM = """你是高中数学答案生成助手。
任务:在录入环节题目缺少答案时,根据题干、可选参考材料与可选全网搜索摘要,生成“答案/最终结果”和足够详细的推导依据。
要求:
- answer 字段优先给出最终答案/最终结果,必要时包含 LaTeX,保持简洁明确。
- analysis_steps 必须详实,不少于 4 个步骤或等价信息量:审题与条件整理、关键转化/公式、计算推导、结果验证/取舍、易错点或不确定性说明。
- 若提供“全网搜索参考”,只能作为核验和补充思路,不得直接照抄;应在 analysis_steps 末尾简要列出采用/未采用的搜索依据标题。
- 若题目信息不足,也要给出最可能答案,同时在 analysis_steps 说明缺失信息和假设,并降低 confidence。
- 不要冒充官方解析;这是系统自动生成的参考答案草稿。
- 输出必须是严格 JSON,不含其它文本。
"""


def answer_user_prompt(
    stem: str,
    subject_area: str,
    reference: str | None = None,
    web_context: str | None = None,
) -> str:
    ref = reference or "(无参考材料)"
    web = web_context or "(未启用或未取得全网搜索参考)"
    return f"""所属模块:{subject_area}

题干(LaTeX/文本):
{stem}

可选参考材料:
{ref}

全网搜索参考:
{web}

请输出 JSON,字段:
- answer: 答案/最终结果,可含 LaTeX
- analysis_steps: 详细推导步骤,需要覆盖审题、转化、计算、验证、易错点/假设;若使用全网搜索参考,列出参考来源标题
- confidence: 0 到 1 的置信度
"""
