"""方法库浏览路由:列表 + 详情 + 例题详情。"""

import json
import re
from typing import Optional
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func
from sqlmodel import Session

from ..deps import get_session_dep, llm_dep
from ..app import templates
from ...config.settings import get_settings
from ...search import WebSearchError, discover_method_candidates
from ...models import (
    Method, MethodStatus, SubjectArea, SolutionInstance, ReviewStatus, Problem,
)


router = APIRouter()


def _split_text(text: str | None) -> list[str]:
    """把多行/序号/分号描述整理成可展示要点。"""
    if not text:
        return []
    raw_parts: list[str] = []
    for line in text.replace("\r", "\n").split("\n"):
        raw_parts.extend(re.split(r"[；;]", line))
    parts = []
    for part in raw_parts:
        item = re.sub(r"^\s*(?:\d+[\.、)]|[-*•])\s*", "", part).strip()
        if item:
            parts.append(item)
    return parts


def _conditions_for(method: Method) -> list[str]:
    """方法实施条件：优先使用 applicability，不足时补学习型检查项。"""
    conditions = _split_text(method.applicability)
    fallbacks_by_area = {
        SubjectArea.DERIVATIVE: [
            "题目目标可转化为函数单调性、最值、零点或恒成立问题。",
            "关键式子允许求导、构造辅助函数或分离参数。",
            "能明确变量范围，并检查端点、等号成立与参数取值边界。",
        ],
        SubjectArea.SEQUENCE: [
            "题目包含递推、通项、求和或放缩比较结构。",
            "可识别首项、公差/公比、递推不变量或可归纳关系。",
            "需要验证初始项、递推合法性与边界项。",
        ],
        SubjectArea.CONIC: [
            "几何关系能转化为坐标、斜率、距离、面积或轨迹方程。",
            "图形中关键点、直线/曲线与参数关系明确。",
            "计算过程中需保留图形约束，排除代数增根。",
        ],
        SubjectArea.PROBABILITY: [
            "事件、随机变量或计数对象可清晰分层。",
            "能够判断独立、互斥、条件概率或分布模型是否成立。",
            "需要核对样本空间完整性与边界情形。",
        ],
        SubjectArea.OTHER: [
            "题目结构与方法核心思想存在可迁移对应关系。",
            "已知条件足以支撑通用步骤中的关键转化。",
            "完成后可用原题条件回代验证结果。",
        ],
    }
    for item in fallbacks_by_area.get(method.subject_area, fallbacks_by_area[SubjectArea.OTHER]):
        if item not in conditions:
            conditions.append(item)
        if len(conditions) >= 5:
            break
    return conditions


def _extend_unique(items: list[str], additions: list[str], *, limit: int = 7) -> list[str]:
    """追加不重复的学习步骤，避免页面出现空洞的“暂无”。"""
    out = [item for item in items if item]
    normalized = {re.sub(r"\s+", "", item) for item in out}
    for item in additions:
        key = re.sub(r"\s+", "", item)
        if key and key not in normalized:
            out.append(item)
            normalized.add(key)
        if len(out) >= limit:
            break
    return out


def _generic_procedure_steps_for(method: Method) -> list[str]:
    """按方法名称/板块给出可学习、可应证的通用解题步骤。"""
    name = method.name or ""
    if "分离参数" in name:
        return [
            "审题定位：确认题目属于含参不等式、恒成立/存在性、零点个数或最值范围问题，标清主变量与参数范围。",
            "等价变形：在定义域、不等号方向、分母正负等条件可控的前提下，把参数项与主变量项分离。",
            "转化目标：把原命题化为参数与函数取值范围的比较，如 a ≥ max g(x)、a ≤ min g(x) 或 a ∈ Range(g)。",
            "研究函数：对分离出的函数求导，结合单调区间、极值点、端点和不可导点确定最值/范围。",
            "回代应证：把参数结论代回原题，检查等号成立、端点、边界参数与变形过程是否引入增漏。",
        ]
    if "切线" in name or "放缩" in name:
        return [
            "识别结构：找出指数、对数、三角或根式等难直接比较的核心函数，判断目标需要上界还是下界。",
            "选择模板：选取切线不等式、经典放缩或局部估计，并写清放缩成立的区间与等号条件。",
            "方向校验：确认放缩方向与证明目标一致，必要时通过作差函数求导验证该不等式。",
            "代入推进：把复杂项替换为可控上/下界，整理成可证明的单调性、最值或代数不等式。",
            "应证收尾：核对等号条件、变量范围和放缩强度，确保没有因放得过粗导致结论断裂。",
        ]
    if "构造" in name:
        return [
            "抽取同构：观察题目中的差值、比值、参数式或两端表达，寻找可统一成同一函数的结构。",
            "定义辅助函数：明确自变量、定义域和比较对象，构造 F(x)、差函数或比值函数。",
            "导数分析：计算导数并判定单调性/凸凹性/极值，必要时继续构造二级辅助函数。",
            "回到目标：把函数性质翻译回原不等式、方程根或大小关系，说明关键点处取等或取界。",
            "验证边界：检查端点、特殊值、参数临界点与定义域限制，避免构造函数只在局部有效。",
        ]
    if "隐零点" in name or "零点" in name:
        return [
            "设定隐点：把无法显式求出的极值点/零点记为 x0，并写出其满足的方程与范围。",
            "方程消元：利用 f'(x0)=0 或 f(x0)=0 消去超越项、参数项或高次项。",
            "转化表达：把待求最值/证明式改写成只含 x0 或更简单参数的函数。",
            "研究范围：根据隐点方程确定 x0 的取值区间，再讨论新函数的单调性或最值。",
            "回代检验：确认隐点存在唯一性、对应参数合法性以及原函数端点是否也参与最值。",
        ]
    if "设而不求" in name or "韦达" in name:
        return [
            "建系设元：保留原图关键关系，设直线/点坐标参数，写清斜率不存在等特殊情形。",
            "联立降维：将直线与圆锥曲线联立成一元二次方程，不急于求交点坐标。",
            "韦达表达：用根和、根积表示弦长、中点、面积、斜率或目标式中的交点关系。",
            "代入目标：把几何条件转为参数方程/不等式，化简求出目标量或参数范围。",
            "几何应证：检查判别式、点在线上/曲线上、图形位置和退化情形，排除代数增根。",
        ]
    if "点差" in name:
        return [
            "设两端点：设弦端点坐标并写出它们分别满足的圆锥曲线方程。",
            "作差整理：两式相减，提取中点坐标、斜率或对称关系。",
            "转为条件：把题给中点、垂直、斜率或定值关系代入点差式。",
            "求解参数：结合直线方程、曲线方程和判别式求轨迹或参数范围。",
            "特殊检验：单独讨论斜率不存在、弦退化、端点重合和图形范围限制。",
        ]
    if "齐次" in name or "平移" in name:
        return [
            "识别非标准形：判断曲线或方程是否可通过配方、平移、旋转转成标准结构。",
            "完成变换：写出新旧坐标/参数关系，并在新坐标系中重写方程与条件。",
            "套用标准结论：在标准型下处理焦点、准线、斜率、弦长或轨迹关系。",
            "反代回原系：把新坐标结果转换回原变量，保持题目要求的表达形式。",
            "校验对应：检查平移前后图形位置、定义域和题设点线关系是否一一对应。",
        ]

    by_area = {
        SubjectArea.DERIVATIVE: [
            "审题识别：判断题目目标是单调性、最值、恒成立、零点还是参数范围，并标注定义域。",
            "关键转化：选择分离参数、构造函数、作差比较、切线放缩或隐零点等入口，把题目转成函数性质问题。",
            "导数推进：求导并分析符号变化，必要时二次求导或引入辅助函数处理导数符号。",
            "得到结论：由单调区间、极值、端点值或零点分布推出答案/参数范围。",
            "结果应证：回代原题检查等号、端点、定义域、参数边界和变形等价性。",
        ],
        SubjectArea.SEQUENCE: [
            "审题识别：明确要求通项、求和、证明不等式还是递推性质，写出初始项和递推范围。",
            "寻找结构：判断可用累加/累乘、待定系数、构造新数列、数学归纳或放缩估计。",
            "建立关系：把递推式改写为可迭代、可求和或可比较的标准形式。",
            "推进计算：求通项/和式/界，并在关键步骤保留 n 的取值条件。",
            "验证边界：检查首项、小 n、等号条件和递推过程是否对所有目标项有效。",
        ],
        SubjectArea.CONIC: [
            "读图建模：保留题图中的点、线、焦点、弦、中点、切线等关系，选择坐标系和参数。",
            "代数转化：将几何条件写成方程、斜率、距离、面积或韦达关系。",
            "消元求解：通过联立、设而不求、点差或参数化减少未知量。",
            "回译结论：把代数结果解释为题目要求的轨迹、定值、范围或位置关系。",
            "图形校验：检查判别式、特殊斜率、点的位置、退化图形和增根。",
        ],
        SubjectArea.PROBABILITY: [
            "审题分层：明确随机试验、样本空间、事件关系或随机变量定义。",
            "选择模型：判断使用排列组合、条件概率、独立性、二项/超几何/正态分布或期望方差公式。",
            "列式计算：按互斥分类、分步乘法或条件链式概率组织计算。",
            "合并化简：求概率、分布列、期望或方差，并保证所有情形不重不漏。",
            "合理性检验：检查概率和为 1、取值范围、独立/互斥假设和边界事件。",
        ],
    }
    return by_area.get(method.subject_area, [
        "审题识别：提取已知条件、目标结论、变量范围和隐藏约束。",
        "匹配方法：判断本方法的适用条件是否满足，找出题目中对应的关键结构。",
        "关键转化：把原问题转成该方法擅长处理的函数、方程、图形、计数或不等式模型。",
        "步骤推进：按核心思想完成计算/证明，记录每一步使用的条件。",
        "方法应证：回到原题检查答案、边界、特殊情形和等价变形，确认方法闭环。",
    ])


def _procedure_steps_for(method: Method) -> list[str]:
    """展示足够详实的通用解题步骤；原始步骤太短时自动补齐。"""
    explicit = _split_text(method.procedure_steps)
    generic = _generic_procedure_steps_for(method)
    if not explicit:
        return generic
    # 旧种子或候选方法常只有“整理/分离/求最值”这类短词，展示时补成可执行清单。
    if len(explicit) < 5 or sum(len(x) for x in explicit) < 80:
        return _extend_unique(explicit, generic, limit=7)
    return explicit


def _dict_from_llm_raw(raw_text: str | None) -> dict:
    if not raw_text:
        return {}
    try:
        raw = json.loads(raw_text)
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _theorem_entry(
    *,
    level: str,
    name: str = "",
    statement: str = "",
    source: str = "",
    example_id: int | None = None,
) -> dict[str, str | int | None]:
    text = (statement or name or "").strip()
    title = (name or "").strip()
    # 支持“定理名：内容”这种单字段录入。
    if not statement and "：" in title:
        head, tail = title.split("：", 1)
        if any(k in head for k in ("定理", "引理", "推论", "公式", "结论", "法则")):
            title, text = head.strip(), tail.strip()
    elif not statement and ":" in title:
        head, tail = title.split(":", 1)
        if any(k in head for k in ("定理", "引理", "推论", "公式", "结论", "法则")):
            title, text = head.strip(), tail.strip()
    return {
        "level": level,
        "name": title or text[:36],
        "statement": text,
        "source": source,
        "example_id": example_id,
    }


def _append_theorem(entries: list[dict], seen: set[str], entry: dict) -> None:
    name = str(entry.get("name") or "").strip()
    statement = str(entry.get("statement") or "").strip()
    if not name and not statement:
        return
    key = re.sub(r"\s+", "", f"{entry.get('level')}|{name}|{statement}")[:180]
    if key in seen:
        return
    seen.add(key)
    entries.append(entry)


def _theorem_mentions_from_text(text: str | None, *, source: str, example_id: int | None = None) -> list[dict]:
    """从关键步骤/迁移说明中兜底抽取显式写出的定理、引理、推论。"""
    if not text:
        return []
    result = []
    keywords = ("定理", "二级定理", "引理", "推论", "公式", "常用结论", "法则")
    parts = _split_text(text)
    for part in parts:
        if any(k in part for k in keywords):
            level = "二级定理/推论" if any(k in part for k in ("二级定理", "引理", "推论", "常用结论")) else "关键定理"
            result.append(_theorem_entry(level=level, name=part[:48], statement=part, source=source, example_id=example_id))
    return result


def _secondary_values(raw_value) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return [str(x).strip() for x in raw_value if str(x).strip()]
    if isinstance(raw_value, str):
        return _split_text(raw_value)
    return [str(raw_value).strip()] if str(raw_value).strip() else []


def _theorems_for(method: Method, sis: list[SolutionInstance], children: list[Method]) -> list[dict]:
    """汇总方法自身、子方法/二级定理、LLM 原始输出和例题步骤中的定理信息。"""
    entries: list[dict] = []
    seen: set[str] = set()

    if getattr(method, "key_theorem", ""):
        _append_theorem(seen=seen, entries=entries, entry=_theorem_entry(
            level="关键定理/更优定理",
            name=method.key_theorem,
            source="方法库维护",
        ))
    for item in _split_text(getattr(method, "secondary_theorems", "")):
        _append_theorem(seen=seen, entries=entries, entry=_theorem_entry(
            level="二级定理/推论",
            name=item,
            source="方法库维护",
        ))

    for child in children:
        if any(k in child.name for k in ("定理", "引理", "推论", "公式", "结论")):
            _append_theorem(seen=seen, entries=entries, entry=_theorem_entry(
                level="二级定理/子方法",
                name=child.name,
                statement=child.core_idea or child.applicability,
                source="子方法",
            ))

    for si in sis:
        raw = _dict_from_llm_raw(si.llm_raw)
        source = f"例题 #{si.problem_id}"
        theorem_name = raw.get("key_theorem") or raw.get("theorem_name") or raw.get("better_theorem") or raw.get("theorem")
        theorem_statement = raw.get("theorem_statement") or raw.get("theorem_detail") or ""
        if theorem_name or theorem_statement:
            _append_theorem(seen=seen, entries=entries, entry=_theorem_entry(
                level="关键定理/更优定理",
                name=str(theorem_name or ""),
                statement=str(theorem_statement or theorem_name or ""),
                source=source,
                example_id=si.problem_id,
            ))
        for key in ("secondary_theorems", "sub_theorems", "lemmas", "corollaries"):
            for value in _secondary_values(raw.get(key)):
                _append_theorem(seen=seen, entries=entries, entry=_theorem_entry(
                    level="二级定理/推论",
                    name=value,
                    source=source,
                    example_id=si.problem_id,
                ))
        for entry in _theorem_mentions_from_text(si.key_steps, source=source, example_id=si.problem_id):
            _append_theorem(seen=seen, entries=entries, entry=entry)
        for entry in _theorem_mentions_from_text(si.transfer_note, source=source, example_id=si.problem_id):
            _append_theorem(seen=seen, entries=entries, entry=entry)

    # 方法描述里如果本来就写了“XX 定理/推论”，也兜底展示。
    for text, source in (
        (method.core_idea, "核心思想"),
        (method.procedure_steps, "通用步骤"),
        (method.applicability, "适用条件"),
    ):
        for entry in _theorem_mentions_from_text(text, source=source):
            _append_theorem(seen=seen, entries=entries, entry=entry)

    return entries[:12]



def _author_thinking_for(method: Method, examples: list[dict], conditions: list[str]) -> dict[str, list[str]]:
    """生成方法详情页的出题人思维分析。

    优先展示人工维护内容；没有维护时，根据方法条件、核心思想和已确信例题
    给出学习者可用的命题意图、设陷方式与破题观察点。
    """
    manual = _split_text(getattr(method, "author_thinking_analysis", ""))
    name = method.name or "该方法"
    area = method.subject_area
    intent = [
        f"命题人通常用“{name}”考查学生能否从题面条件中识别关键结构，而不是直接套模板。",
    ]
    if method.core_idea:
        intent.append(f"核心考查点：{method.core_idea[:120]}{'…' if len(method.core_idea) > 120 else ''}")
    elif method.applicability:
        intent.append(f"常见切入点：先识别适用特征——{method.applicability[:120]}{'…' if len(method.applicability) > 120 else ''}")
    if area in (SubjectArea.CONIC, SubjectArea.PLANE_GEOMETRY, SubjectArea.SOLID_GEOMETRY):
        intent.append("几何类题目往往把关键关系藏在图形、辅助线、特殊点或坐标约束中，要求保留图形信息并转化为可计算关系。")
    elif area == SubjectArea.DERIVATIVE:
        intent.append("导数类题目常把参数、恒成立、零点或最值目标包装在复杂式子里，要求先完成函数化和范围化。")
    elif area == SubjectArea.SEQUENCE:
        intent.append("数列类题目常通过递推、求和或放缩制造层次，要求找不变量、单调性或可归纳结构。")

    traps = []
    for p in _split_text(method.pitfalls)[:3]:
        traps.append(f"显性陷阱：{p}")
    if conditions:
        traps.append(f"隐性门槛：至少要满足“{conditions[0]}”，否则看似同类也不能直接套用。")
    if method.key_theorem:
        traps.append(f"定理选择：题目可能用常规定理作干扰，真正高效的抓手是“{method.key_theorem}”。")
    if not traps:
        traps.extend([
            "题干可能故意给出多余条件，先判断哪些条件服务于核心转化，哪些只是计算干扰。",
            "注意定义域、端点、等号成立条件和图形约束；这些通常是区分完整解与漏解的地方。",
        ])

    breakthrough = []
    if examples:
        e = examples[0]
        clue = e.get("transfer_note") or e.get("key_steps") or e.get("summary") or ""
        if clue:
            breakthrough.append(f"对照例题 #{e['id']}：命题突破口通常落在“{clue[:120]}{'…' if len(clue) > 120 else ''}”。")
        breakthrough.append(f"已确信例题数量为 {len(examples)}，可逐题比较题面变化与同一方法条件之间的对应关系。")
    if method.procedure_steps:
        steps = _split_text(method.procedure_steps)
        if steps:
            breakthrough.append(f"破题顺序建议先抓第一步：{steps[0]}")
    if not breakthrough:
        breakthrough.extend([
            "先问：题目想让我把什么对象转化成可比较、可求最值或可验证的形式？",
            "再问：如果直接计算很繁，是否说明命题人希望我使用结构识别、定理替换或辅助对象？",
        ])

    return {
        "manual": manual,
        "intent": intent[:4],
        "traps": traps[:5],
        "breakthrough": breakthrough[:4],
    }



def _variant_self_tests_for(method: Method, examples: list[dict], *, count: int = 3) -> list[dict[str, str]]:
    """基于方法模板反向生成同类型自测变式题。"""
    name = method.name or "该方法"
    area = method.subject_area
    sample = examples[0] if examples else {}
    sample_tags = sample.get("problem_type_tags") or sample.get("sub_knowledge") or method.applicability or "同类结构"
    base_requirements = [
        "先判断是否满足方法适用条件，再动手计算。",
        "解答后必须回代检查边界、等号和特殊情形。",
    ]
    if "分离参数" in name or area == SubjectArea.DERIVATIVE:
        templates = [
            {
                "title": "自测变式 A：恒成立参数范围",
                "stem": "设函数 f(x)=e^x-ax 在给定区间上满足 f(x)≥m。请确定参数 a 的取值范围，并说明端点是否取等。",
                "check": "能否把参数项分离成 a 与某个函数最值的比较。",
            },
            {
                "title": "自测变式 B：零点个数反推参数",
                "stem": "已知含参函数在区间内有且仅有一个零点。请用导数研究单调性，并求参数范围。",
                "check": "能否把零点个数转化为极值、端点符号与参数范围的联合判断。",
            },
            {
                "title": "自测变式 C：不等式证明升级",
                "stem": "证明一个含参数不等式对所有 x 成立，并找出参数的最优上界或下界。",
                "check": "能否避免直接硬算，先抽出主变量函数并求最值。",
            },
        ]
    elif area in (SubjectArea.CONIC, SubjectArea.PLANE_GEOMETRY, SubjectArea.SOLID_GEOMETRY):
        templates = [
            {
                "title": "自测变式 A：保留题图的弦长问题",
                "stem": "给定圆锥曲线与过定点直线相交于两点，求弦长或面积的取值范围。请保留图形约束。",
                "check": "能否用设而不求/韦达关系表达交点关系，并排除退化位置。",
            },
            {
                "title": "自测变式 B：中点或斜率条件",
                "stem": "已知弦的中点或两条直线斜率关系，求轨迹方程或参数范围。",
                "check": "能否把几何关系转化为点差、斜率或坐标方程。",
            },
            {
                "title": "自测变式 C：定值/定点验证",
                "stem": "在变化直线或动点条件下判断某量是否为定值，并给出证明。",
                "check": "能否发现不变量，而不是盲目展开全部坐标。",
            },
        ]
    else:
        templates = [
            {
                "title": "自测变式 A：条件替换",
                "stem": f"保持“{name}”的核心结构不变，将题目目标从求值改为求范围或证明。",
                "check": "能否识别题面改变后仍可使用同一关键转化。",
            },
            {
                "title": "自测变式 B：反向设问",
                "stem": "把原题结论作为条件之一，反求参数、初值或图形位置。",
                "check": "能否从结论倒推到方法模板中的关键步骤。",
            },
            {
                "title": "自测变式 C：边界强化",
                "stem": "加入端点、临界值或特殊位置，判断原方法是否仍然有效。",
                "check": "能否主动检验适用条件，避免过度套用。",
            },
        ]
    out = []
    for idx, item in enumerate(templates[:max(1, min(count, 5))], start=1):
        out.append({
            "title": item["title"],
            "stem": item["stem"],
            "template_source": f"方法模板：{name}；参考标签：{sample_tags}",
            "self_check": item["check"],
            "requirements": "；".join(base_requirements),
            "difficulty": ["基础迁移", "中档综合", "压轴挑战"][min(idx - 1, 2)],
        })
    return out


def _error_graph_for(method: Method, sis: list[SolutionInstance], rejected_sis: list[SolutionInstance]) -> dict[str, list[dict[str, str]]]:
    """构造错因图谱/负例知识库。"""
    nodes: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(step: str, error: str, fix: str, source: str) -> None:
        key = re.sub(r"\s+", "", f"{step}|{error}")[:160]
        if not error or key in seen:
            return
        seen.add(key)
        nodes.append({"step": step, "error": error, "fix": fix, "source": source})

    for idx, pitfall in enumerate(_split_text(method.pitfalls), start=1):
        add(f"方法易错点 {idx}", pitfall, "回到适用条件和验证清单逐项检查。", "方法库维护")

    for si in sis + rejected_sis:
        raw = _dict_from_llm_raw(si.llm_raw)
        for key in ("common_errors", "error_points", "pitfalls", "misconceptions", "negative_examples"):
            for value in _secondary_values(raw.get(key)):
                add("例题演绎", value, "对照官方解析步骤，标出错误发生前的必要条件。", f"例题 #{si.problem_id}")
        if si.reviewer_note and si.review_status == ReviewStatus.REJECTED:
            add("审核负例", si.reviewer_note, "不要把该解法作为通用模板；先确认方法归属和关键条件。", f"被拒样本 #{si.problem_id}")

    if method.key_theorem:
        add("定理调用", f"把“{method.key_theorem}”当作万能结论，忽略其成立条件。", "使用定理前先写明连续性、可导性、区间或图形前提。", "规则生成")
    if not nodes:
        add("识别阶段", "只看到题面相似就套方法，未核对适用条件。", "先用“实现该方法的条件”逐条打勾。", "规则生成")
        add("收尾阶段", "算出结果后未检查端点、等号、定义域或图形退化。", "把结论代回原题，单独验证边界与特殊情形。", "规则生成")
    return {"nodes": nodes[:8]}


def _cross_year_trend_for(method: Method, examples: list[dict]) -> dict[str, object]:
    """按同一方法/知识点的已确信例题，给出近 5-10 年趋势判断。"""
    years = sorted({int(e["year"]) for e in examples if e.get("year")})
    recent = [y for y in years if y >= (max(years) - 9)] if years else []
    tags: dict[str, int] = {}
    for e in examples:
        for part in _split_text(";".join([e.get("sub_knowledge") or "", e.get("problem_type_tags") or ""])):
            tags[part] = tags.get(part, 0) + 1
    top_tags = sorted(tags.items(), key=lambda kv: (-kv[1], kv[0]))[:4]
    bullets: list[str] = []
    if recent:
        bullets.append(f"样本年份覆盖 {min(recent)}–{max(recent)}，近 10 年内命中 {len(recent)} 个年份。")
        if len(recent) >= 3:
            bullets.append("该方法在近年样本中持续出现，暂不宜视为过时；重点关注题面包装和定理选择是否升级。")
        else:
            bullets.append("近年样本偏少，不能仅凭当前库判断热度；建议继续补充近 5 年真题后再做趋势结论。")
    else:
        bullets.append("暂无跨年 confirmed 样本，趋势判断需要更多历史题支撑。")
    if top_tags:
        bullets.append("高频关联知识点：" + "、".join(f"{k}({v})" for k, v in top_tags))
    if method.key_theorem or method.secondary_theorems:
        bullets.append("若近年题目引入更优定理/二级定理，应优先比较新定理是否缩短步骤，判断方法是否发生“升级”。")
    return {
        "years": recent,
        "bullets": bullets,
        "status": "持续有效" if len(recent) >= 3 else "样本不足",
    }


def _explanation_styles_for(method: Method, procedure_steps: list[str], conditions: list[str]) -> list[dict[str, object]]:
    """同一方法卡片的三种讲解风格。"""
    name = method.name or "该方法"
    first_step = procedure_steps[0] if procedure_steps else "先识别题目中的关键结构。"
    condition = conditions[0] if conditions else "题目结构满足本方法适用条件。"
    return [
        {
            "name": "直觉理解版",
            "summary": f"把“{name}”理解成：先看题目想把你引向哪个核心结构，再把复杂条件改写成熟悉模型。",
            "points": [f"第一眼先找：{condition}", f"破题动作：{first_step}", "如果计算越来越复杂，通常说明还没有抓到正确结构。"],
        },
        {
            "name": "严谨证明版",
            "summary": f"使用“{name}”时，需要逐条声明适用前提、等价变形和边界检验。",
            "points": ["写清变量范围、定义域和图形/参数约束。", "每一步转化都标明依据的定理、单调性或代数等价关系。", "结论必须回代验证，尤其是端点、等号和退化情形。"],
        },
        {
            "name": "口诀记忆版",
            "summary": "识别结构 → 关键转化 → 推进计算 → 回代验证。",
            "points": ["先判能不能用。", "再找最省力的转化。", "最后查边界、等号、反例。"],
        },
    ]


def _confidence_annotation_for(method: Method, sis: list[SolutionInstance], rejected_sis: list[SolutionInstance], examples: list[dict]) -> dict[str, object]:
    """给通用解法标注覆盖题数、反例和泛化风险。"""
    confirmed_count = len(examples)
    rejected_count = len(rejected_sis)
    avg_conf = None
    if sis:
        avg_conf = round(sum(float(si.confidence or 0) for si in sis) / len(sis), 2)
    if confirmed_count >= 5 and rejected_count == 0:
        level = "高"
        warning = "覆盖样本较多且暂无明确反例，但仍需核对适用条件。"
    elif confirmed_count >= 2:
        level = "中"
        warning = "已有多个历史样本支持，仍不应外推到条件不匹配的题型。"
    else:
        level = "低"
        warning = "覆盖样本少，当前通用解法更像学习假设，需用更多例题验证。"
    counterexamples = []
    for si in rejected_sis[:3]:
        counterexamples.append({
            "problem_id": si.problem_id,
            "reason": si.reviewer_note or "审核拒绝/方法不匹配，不能作为该方法正例。",
        })
    return {
        "level": level,
        "confirmed_count": confirmed_count,
        "rejected_count": rejected_count,
        "avg_confidence": avg_conf,
        "warning": warning,
        "counterexamples": counterexamples,
    }
def _variants_for(method: Method, children: list[Method], related: list[Method]) -> list[dict[str, str]]:
    """构造举一反三变式：子方法/近邻方法优先，再补一个启发式变式。"""
    variants: list[dict[str, str]] = []
    for child in children[:2]:
        variants.append({
            "title": f"子方法变式：{child.name}",
            "focus": child.core_idea or child.applicability or "沿用当前方法核心思想，换用更细分的处理路径。",
            "use_when": child.applicability or "当题目条件更贴近该子方法的适用特征时使用。",
        })

    name = method.name
    if "分离参数" in name:
        heuristic = {
            "title": "举一反三：端点/最值型分离参数变式",
            "focus": "先把参数放到一侧，再把另一侧看作函数，利用导数求最值确定参数范围。",
            "use_when": "适合恒成立、存在性、零点个数变化，以及参数只在不等式一侧稳定出现的题目。",
        }
    elif "构造" in name:
        heuristic = {
            "title": "举一反三：同构构造变式",
            "focus": "把复杂式改写成同一函数结构，构造辅助函数比较两个对象。",
            "use_when": "适合式子形式相似、差值/比值难直接判断，但可归并为同一函数单调性的题目。",
        }
    elif "放缩" in name:
        heuristic = {
            "title": "举一反三：局部放缩到整体估计变式",
            "focus": "先对关键项做可控放缩，再累加或传递得到整体界。",
            "use_when": "适合含和式、乘积、递推估计，以及目标只需要证明范围而非精确值的题目。",
        }
    elif "几何" in name or method.subject_area in (SubjectArea.CONIC, SubjectArea.PLANE_GEOMETRY, SubjectArea.SOLID_GEOMETRY):
        heuristic = {
            "title": "举一反三：图形约束转代数变式",
            "focus": "保留原图关系，把角度、距离、斜率或面积条件转成方程/不等式。",
            "use_when": "适合图形信息强、直接文字化容易丢失条件的解析几何或几何综合题。",
        }
    else:
        heuristic = {
            "title": "举一反三：条件替换变式",
            "focus": "保持当前方法的核心转化不变，替换参数范围、目标结论或等号成立条件。",
            "use_when": "适合题干表面变化较大，但关键结构、约束关系与本方法一致的同类题。",
        }
    if all(v["title"] != heuristic["title"] for v in variants):
        variants.append(heuristic)

    for rel in related[:2]:
        variants.append({
            "title": f"近邻方法对照：{rel.name}",
            "focus": rel.core_idea or "与当前方法同属一个板块，可作为替代思路比较。",
            "use_when": rel.applicability or "当当前方法条件不完全满足时，尝试切换到该近邻方法。",
        })
    return variants[:4]


@router.get("/methods", response_class=HTMLResponse)
async def list_view(
    request: Request,
    area: str = "",
    status: str = "",
    s: Session = Depends(get_session_dep),
):
    stmt = select(Method)
    if area:
        stmt = stmt.where(Method.subject_area == SubjectArea(area))
    if status:
        stmt = stmt.where(Method.status == MethodStatus(status))
    methods = list(s.execute(stmt).scalars().all())
    out = []
    for m in methods:
        count = s.exec(
            select(func.count(SolutionInstance.id)).where(
                SolutionInstance.method_id == m.id,
                SolutionInstance.review_status == ReviewStatus.CONFIRMED,
            )
        ).scalar() or 0
        out.append({
            "id": m.id, "name": m.name, "subject_area": m.subject_area.value,
            "status": m.status.value, "count": int(count),
        })
    return templates.TemplateResponse(request, "methods_list.html", {
        "areas": [a.value for a in SubjectArea],
        "statuses": [st.value for st in MethodStatus],
        "area": area, "status": status, "methods": out,
    })


@router.post("/methods")
async def create_method(
    name: str = Form(...),
    subject_area: str = Form(...),
    status: str = Form(MethodStatus.CONFIRMED.value),
    applicability: str = Form(""),
    core_idea: str = Form(""),
    key_theorem: str = Form(""),
    secondary_theorems: str = Form(""),
    procedure_steps: str = Form(""),
    author_thinking_analysis: str = Form(""),
    pitfalls: str = Form(""),
    s: Session = Depends(get_session_dep),
):
    """方法库手动新增方法。

    默认按 confirmed 入库，便于教研人员直接维护成熟方法；若同板块同名已存在，
    则补充/更新该方法的描述字段并跳转详情，避免重复制造同名方法。
    """
    clean_name = name.strip()
    if not clean_name:
        return HTMLResponse("方法名称不能为空", status_code=400)
    try:
        area_enum = SubjectArea(subject_area)
    except ValueError:
        return HTMLResponse("未知板块", status_code=400)
    try:
        status_enum = MethodStatus(status)
    except ValueError:
        return HTMLResponse("未知状态", status_code=400)

    existing = s.execute(
        select(Method).where(Method.name == clean_name, Method.subject_area == area_enum)
    ).scalars().first()
    target = existing or Method(name=clean_name, subject_area=area_enum)
    target.status = status_enum
    values = {
        "applicability": applicability.strip(),
        "core_idea": core_idea.strip(),
        "key_theorem": key_theorem.strip(),
        "secondary_theorems": secondary_theorems.strip(),
        "procedure_steps": procedure_steps.strip(),
        "author_thinking_analysis": author_thinking_analysis.strip(),
        "pitfalls": pitfalls.strip(),
    }
    for field, value in values.items():
        # 新方法允许空字段；同名方法存在时只用非空输入补充/更新，避免误清空。
        if existing is None or value:
            setattr(target, field, value)
    s.add(target)
    s.commit()
    s.refresh(target)
    return RedirectResponse(f"/methods/{target.id}", status_code=303)




@router.get("/methods-discover", response_class=HTMLResponse)
@router.get("/methods/discover", response_class=HTMLResponse)
async def discover_methods_view(
    request: Request,
    query: str = "",
    area: str = "导数",
    max_results: int = 5,
    s: Session = Depends(get_session_dep),
):
    """通过全网搜索 API 发现可加入方法库的候选方法。"""
    candidates = []
    error = ""
    area_value = area or SubjectArea.DERIVATIVE.value
    try:
        area_enum = SubjectArea(area_value)
    except ValueError:
        area_enum = SubjectArea.OTHER
        area_value = area_enum.value
    if query.strip():
        try:
            candidates = discover_method_candidates(
                query=query,
                area=area_enum,
                settings=get_settings().web_search,
                max_results=max(1, min(max_results, 10)),
            )
        except WebSearchError as exc:
            error = str(exc)
    existing_names = {
        (m.name, m.subject_area.value)
        for m in s.execute(select(Method)).scalars().all()
    }
    rows = []
    for c in candidates:
        rows.append({
            "name": c.name,
            "subject_area": c.subject_area.value,
            "applicability": c.applicability,
            "core_idea": c.core_idea,
            "key_theorem": c.key_theorem,
            "secondary_theorems": c.secondary_theorems,
            "procedure_steps": c.procedure_steps,
            "pitfalls": c.pitfalls,
            "source_title": c.source_title,
            "source_url": c.source_url,
            "exists": (c.name, c.subject_area.value) in existing_names,
        })
    return templates.TemplateResponse(request, "method_discover.html", {
        "areas": [a.value for a in SubjectArea],
        "query": query,
        "area": area_value,
        "max_results": max_results,
        "candidates": rows,
        "error": error,
        "search_settings": get_settings().web_search,
    })


@router.post("/methods-discover/add")
@router.post("/methods/discover/add")
async def add_discovered_method(
    name: str = Form(...),
    subject_area: str = Form(...),
    applicability: str = Form(""),
    core_idea: str = Form(""),
    key_theorem: str = Form(""),
    secondary_theorems: str = Form(""),
    procedure_steps: str = Form(""),
    pitfalls: str = Form(""),
    source_url: str = Form(""),
    status: str = Form(MethodStatus.CANDIDATE.value),
    s: Session = Depends(get_session_dep),
):
    """把全网搜索发现的方法加入方法库，默认作为 candidate 供后续复核。"""
    clean_name = name.strip()
    if not clean_name:
        return HTMLResponse("方法名称不能为空", status_code=400)
    try:
        area_enum = SubjectArea(subject_area)
    except ValueError:
        area_enum = SubjectArea.OTHER
    try:
        status_enum = MethodStatus(status)
    except ValueError:
        status_enum = MethodStatus.CANDIDATE
    existing = s.execute(
        select(Method).where(Method.name == clean_name, Method.subject_area == area_enum)
    ).scalars().first()
    target = existing or Method(name=clean_name, subject_area=area_enum)
    if existing is None:
        target.status = status_enum
    elif existing.status == MethodStatus.CANDIDATE and status_enum == MethodStatus.CONFIRMED:
        target.status = MethodStatus.CONFIRMED
    source_note = f"\n\n全网搜索来源：{source_url}" if source_url and source_url not in core_idea else ""
    values = {
        "applicability": applicability.strip(),
        "core_idea": (core_idea.strip() + source_note).strip(),
        "key_theorem": key_theorem.strip(),
        "secondary_theorems": secondary_theorems.strip(),
        "procedure_steps": procedure_steps.strip(),
        "pitfalls": pitfalls.strip(),
    }
    for field, value in values.items():
        if existing is None or value:
            setattr(target, field, value)
    s.add(target)
    s.commit()
    s.refresh(target)
    return RedirectResponse(f"/methods/{target.id}", status_code=303)


@router.get("/methods/{method_id}", response_class=HTMLResponse)
async def detail_view(
    request: Request,
    method_id: int,
    generate_variants: int = 0,
    variant_count: int = 3,
    s: Session = Depends(get_session_dep),
):
    method = s.get(Method, method_id)
    if method is None:
        return HTMLResponse("Method not found", status_code=404)
    sis = list(s.execute(
        select(SolutionInstance).where(
            SolutionInstance.method_id == method_id,
            SolutionInstance.review_status == ReviewStatus.CONFIRMED,
        )
    ).scalars().all())
    rejected_sis = list(s.execute(
        select(SolutionInstance).where(
            SolutionInstance.method_id == method_id,
            SolutionInstance.review_status == ReviewStatus.REJECTED,
        )
    ).scalars().all())
    examples = []
    for si in sis:
        p = s.get(Problem, si.problem_id)
        if p is None:
            continue
        examples.append({
            "id": p.id,
            "year": p.year,
            "region": p.region,
            "stem_latex": p.stem_latex,
            "answer": p.answer,
            "official_analysis_steps": p.official_analysis_steps or p.reference_solution or "",
            "image_ref": p.image_ref,
            "sub_knowledge": p.sub_knowledge,
            "problem_type_tags": p.problem_type_tags,
            "summary": (si.transfer_note or si.key_steps or p.stem_latex)[:90],
            "key_steps": si.key_steps,
            "transfer_note": si.transfer_note,
        })

    children = list(s.execute(
        select(Method).where(Method.parent_id == method_id)
    ).scalars().all())
    related = list(s.execute(
        select(Method).where(
            Method.subject_area == method.subject_area,
            Method.id != method_id,
            Method.status.in_([MethodStatus.CONFIRMED, MethodStatus.SEED]),
        ).limit(4)
    ).scalars().all())

    conditions = _conditions_for(method)
    procedure_steps = _procedure_steps_for(method)
    generated_variants = _variant_self_tests_for(method, examples, count=variant_count) if generate_variants else []
    return templates.TemplateResponse(request, "method_detail.html", {
        "method": method,
        "examples": examples,
        "conditions": conditions,
        "author_thinking": _author_thinking_for(method, examples, conditions),
        "core_points": _split_text(method.core_idea),
        "procedure_steps": procedure_steps,
        "pitfalls": _split_text(method.pitfalls),
        "theorems": _theorems_for(method, sis, children),
        "variants": _variants_for(method, children, related),
        "generated_variants": generated_variants,
        "show_generated_variants": bool(generate_variants),
        "error_graph": _error_graph_for(method, sis, rejected_sis),
        "cross_year_trend": _cross_year_trend_for(method, examples),
        "explanation_styles": _explanation_styles_for(method, procedure_steps, conditions),
        "confidence_annotation": _confidence_annotation_for(method, sis, rejected_sis, examples),
    })


@router.post("/problems/{problem_id}/generate-answer")
async def generate_problem_answer(
    problem_id: int,
    request: Request,
    s: Session = Depends(get_session_dep),
    llm=Depends(llm_dep),
):
    """为已入库例题手动调用 LLM/API 生成或更新答案与解析草稿。"""
    problem = s.get(Problem, problem_id)
    if problem is None:
        return HTMLResponse("Problem not found", status_code=404)

    from .ingest import _generate_missing_answer_fail_open

    reference = problem.official_analysis_steps or problem.reference_solution or None
    generated, llm_warning, search_notice = _generate_missing_answer_fail_open(
        llm,
        stem_latex=problem.stem_latex,
        subject_area=problem.subject_area.value,
        reference_solution=reference,
    )
    problem.answer = (generated.answer or "").strip() or problem.answer
    if generated.analysis_steps:
        problem.official_analysis_steps = generated.analysis_steps.strip()
        problem.reference_solution = generated.analysis_steps.strip()
    s.add(problem)
    s.commit()

    flags = ["generated=1"]
    if llm_warning:
        flags.append("llm_fallback=1")
    if search_notice:
        flags.append("search=1")
    return RedirectResponse(
        f"/problems/{problem_id}?" + "&".join(flags),
        status_code=303,
    )


@router.get("/problems/{problem_id}", response_class=HTMLResponse)
async def problem_detail_view(
    request: Request,
    problem_id: int,
    s: Session = Depends(get_session_dep),
):
    problem = s.get(Problem, problem_id)
    if problem is None:
        return HTMLResponse("Problem not found", status_code=404)
    sis = list(s.execute(
        select(SolutionInstance).where(
            SolutionInstance.problem_id == problem_id,
            SolutionInstance.review_status == ReviewStatus.CONFIRMED,
        )
    ).scalars().all())
    solutions = []
    for si in sis:
        method = s.get(Method, si.method_id)
        solutions.append({
            "si": si,
            "method": method,
        })
    return templates.TemplateResponse(request, "problem_detail.html", {
        "problem": problem,
        "solutions": solutions,
        "generated_answer": request.query_params.get("generated") == "1",
        "llm_fallback": request.query_params.get("llm_fallback") == "1",
        "search_used": request.query_params.get("search") == "1",
    })
