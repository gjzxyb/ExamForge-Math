"""数学试题 OCR 文本的保守清洗与 LaTeX 排版。"""

from __future__ import annotations

import re


_CJK = r"\u3400-\u4dbf\u4e00-\u9fff"
_MATH_TOKEN = r"(?:\\[A-Za-z]+|\\[{}|]|[A-Za-z0-9_{}^+\-<>=(),'])"
_MATH_RUN = re.compile(rf"{_MATH_TOKEN}(?:[ \t]*{_MATH_TOKEN})*")
_GEOMETRY_COMMANDS = r"parallel|perp|angle|triangle|arc|cong|sim"
_DELIMITED_MATH = re.compile(r"(\$\$.*?\$\$|\$.*?\$)", re.DOTALL)


def _compact_braced_arg(match: re.Match[str]) -> str:
    command, value = match.group(1), match.group(2)
    return f"\\{command}{{{''.join(value.split())}}}"


def _separate_geometry_commands(text: str) -> str:
    """修复 OCR 把几何 LaTeX 命令与点名粘连后形成的非法命令。"""
    return re.sub(
        rf"\\({_GEOMETRY_COMMANDS})(?=[A-Za-z])",
        r"\\\1 ",
        text,
    )


def _repair_geometry_latex(text: str) -> str:
    """把常见几何符号误识别统一为 MathJax 可解析的 LaTeX。"""
    text = re.sub(
        r"([A-Z](?:')?)[ \t]*(?:Ⅱ|∥|‖)[ \t]*(?=[A-Z]|平面)",
        r"\1\\parallel ",
        text,
    )
    text = re.sub(
        r"([A-Z](?:')?)[ \t]*⊥[ \t]*(?=[A-Z])",
        r"\1\\perp ",
        text,
    )
    text = text.replace("∠", r"\angle ").replace("△", r"\triangle ")
    text = re.sub(
        r"(\d+(?:\.\d+)?)[ \t]*(?:°|º)",
        lambda match: f"{match.group(1)}^\\circ",
        text,
    )
    return _separate_geometry_commands(text)


def _repair_malformed_math_delimiters(text: str) -> str:
    """修复 OCR 把集合花括号与行内公式分隔符混在一起的情况。"""
    return re.sub(
        r"\\left[ \t]*\$[ \t]*\\\$[ \t]*\{"
        r"(?P<body>.*?)"
        r"\\right[ \t]*\$[ \t]*\\\}",
        lambda match: rf"\left\{{{match.group('body').strip()}\right\}}",
        text,
        flags=re.DOTALL,
    )


def _repair_triangle_vertices(text: str) -> str:
    """移除 OCR 为三角形各顶点添加的多余参数花括号。"""
    point = r"[A-Z](?:')?(?:_\s*(?:\{[^{}]+\}|[A-Za-z0-9]+(?:\s*[+\-]\s*\d+)?))?"
    return re.sub(
        rf"\\triangle\s*\{{\s*([^{{}}]+?)\s*\}}"
        rf"\s*\{{\s*([^{{}}]+?)\s*\}}\s*({point})",
        lambda match: "\\triangle " + " ".join(match.groups()),
        text,
    )


_SCALABLE_DELIMITER_TOKEN = (
    r"(?:\\(?:langle|rangle|lbrace|rbrace|vert|Vert)|"
    r"\\[{}|]|\(|\)|\[|\]|\||\.|<|>)"
)
_SCALABLE_COMMAND_RE = re.compile(
    rf"\\(?P<side>left|right)[ \t]*(?P<delimiter>{_SCALABLE_DELIMITER_TOKEN})"
)
_SCALABLE_OPEN_RE = r"(?:\(|\[|\\\{|\\langle|\\lbrace|\||\\vert|\\Vert)"
_SCALABLE_CLOSE_BY_OPEN = {
    "(": ")",
    "[": "]",
    r"\{": r"\}",
    r"\langle": r"\rangle",
    r"\lbrace": r"\rbrace",
    "|": "|",
    r"\vert": r"\vert",
    r"\Vert": r"\Vert",
}
_SCALABLE_DELIMITER_ALIASES = {
    "（": "(",
    "）": ")",
    "［": "[",
    "］": "]",
    "【": "[",
    "】": "]",
    "｛": r"\{",
    "｝": r"\}",
}


def _balance_scalable_delimiters(text: str) -> str:
    """把未成对的 ``\\left``/``\\right`` 降级为普通括号，避免 MathJax 报错。"""
    stack: list[re.Match[str]] = []
    replacements: list[tuple[int, int, str]] = []
    for match in _SCALABLE_COMMAND_RE.finditer(text):
        if match.group("side") == "left":
            stack.append(match)
        elif stack:
            stack.pop()
        else:
            replacements.append((match.start(), match.end(), match.group("delimiter")))
    replacements.extend(
        (match.start(), match.end(), match.group("delimiter"))
        for match in stack
    )
    for start, end, delimiter in sorted(replacements, reverse=True):
        text = text[:start] + delimiter + text[end:]
    return text


def _repair_scalable_delimiters(text: str) -> str:
    """修复 OCR 常见的中文括号及 ``\\right。`` 等非法伸缩定界符。"""
    text = re.sub(
        r"\\(left|right)[ \t]*([（）［］【】｛｝])",
        lambda match: (
            f"\\{match.group(1)}"
            f"{_SCALABLE_DELIMITER_ALIASES[match.group(2)]}"
        ),
        text,
    )

    # OCR 常把右括号识别成句号：``\\left(...\\right。``。
    # 能找到左定界符时补回匹配的右定界符，并把中文标点保留在公式外。
    malformed_right = re.compile(
        rf"\\left(?P<open>{_SCALABLE_OPEN_RE})"
        r"(?P<body>(?:(?!\\left).)*?)"
        r"\\right[ \t]*(?P<punct>[，。；：！？、])",
        re.DOTALL,
    )

    def close_before_punctuation(match: re.Match[str]) -> str:
        opening = match.group("open")
        closing = _SCALABLE_CLOSE_BY_OPEN.get(opening, ")")
        return (
            f"\\left{opening}{match.group('body')}"
            f"\\right{closing}{match.group('punct')}"
        )

    text = malformed_right.sub(close_before_punctuation, text)

    # 左括号存在但右命令完全丢失时，仅在明确的句末标点前补齐，
    # 避免把区间内部的中文逗号误判成结束符。
    missing_right = re.compile(
        rf"\\left(?P<open>{_SCALABLE_OPEN_RE})"
        r"(?P<body>(?:(?!\\left|\\right)[^\n\u3400-\u9fff])*?)"
        r"(?P<punct>[。；！？])"
    )
    text = missing_right.sub(close_before_punctuation, text)

    # 没有左定界符可配对的 ``\\right。`` 直接移除命令，保留句号。
    text = re.sub(r"\\(?:left|right)[ \t]*(?=[，。；：！？、])", "", text)

    # 已经含有 $...$ 的片段分别检查，防止跨公式错误配对。
    parts = _DELIMITED_MATH.split(text)
    return "".join(
        _balance_scalable_delimiters(part)
        for part in parts
    )


def _close_unmatched_inline_math(text: str) -> str:
    """闭合 OCR 遗漏的行内 ``$``，并把句末标点移到公式外。"""
    dollar_positions = [
        match.start()
        for match in re.finditer(r"(?<!\\)\$", text)
    ]
    if len(dollar_positions) % 2 == 0:
        return text

    start = dollar_positions[-1]
    tail = text[start + 1:]
    punctuation = re.search(r"[，。；：！？、]", tail)
    if punctuation:
        body = tail[:punctuation.start()]
        remainder = tail[punctuation.start():]
    else:
        body = tail
        remainder = ""

    # 部分 OCR 会产生 ``${x>0``，这里的孤立左花括号不是有效分组。
    if body.startswith("{") and body.count("{") > body.count("}"):
        body = body[1:]
    return f"{text[:start + 1]}{body}${remainder}"


def _repair_redundant_inline_dollars(text: str) -> str:
    """移除行内公式闭合后多出的 ``$``，不改动 ``$$...$$`` 块公式。"""
    return re.sub(
        r"(?<!\$)(\$[^$\n]+\$)\$+(?=[，。；：！？、\n]|$)",
        r"\1",
        text,
    )


def _compact_latex(text: str) -> str:
    text = re.sub(
        r"\\(operatorname|mathrm|mathbf|mathit|mathcal|mathbb|text)"
        r"\s*\{\s*([^{}]+?)\s*\}",
        _compact_braced_arg,
        text,
    )
    text = re.sub(r"\\([A-Za-z]+)\s*\{\s*", r"\\\1{", text)
    for _ in range(4):
        compacted = re.sub(
            r"\{\s*([^{}]*?)\s*\}",
            lambda m: "{" + m.group(1).strip() + "}",
            text,
        )
        if compacted == text:
            break
        text = compacted
    text = re.sub(r"_\s*\{\s*([^{}]+?)\s*\}", lambda m: "_{" + "".join(m.group(1).split()) + "}", text)
    text = re.sub(r"\^\s*\{\s*([^{}]+?)\s*\}", lambda m: "^{" + "".join(m.group(1).split()) + "}", text)
    text = re.sub(r"[ \t]+([_^])", r"\1", text)
    text = re.sub(r"}[ \t]+{", "}{", text)
    text = re.sub(r"_\{([A-Za-z0-9])\}", r"_\1", text)
    text = re.sub(r"\^\{([A-Za-z0-9])\}", r"^\1", text)
    text = re.sub(r"\\(left|right)\s*([()\[\]|])", r"\\\1\2", text)
    text = re.sub(r"\\left\([ \t]*", r"\\left(", text)
    text = re.sub(r"[ \t]*\\right\)", r"\\right)", text)
    return text


def _repair_sequence_subscripts(text: str) -> str:
    text = re.sub(
        r"(?<![A-Za-z])([pq])\s*_\s*([A-Za-z0-9]+)",
        lambda m: f"{m.group(1)}_{m.group(2)}" if len(m.group(2)) == 1
        else f"{m.group(1)}_{{{m.group(2)}}}",
        text,
    )
    text = re.sub(r"(?<![A-Za-z])([pq])\s*([kK])\b", lambda m: f"{m.group(1)}_{m.group(2).lower()}", text)
    text = re.sub(
        r"(?<![A-Za-z])([pq])\s*((?:\d+)?m(?:\s*[+\-]\s*\d+)?)",
        lambda m: f"{m.group(1)}_{{{''.join(m.group(2).split())}}}",
        text,
    )
    text = re.sub(r"(?<![A-Za-z])([pq])\s*(\d+)\b", r"\1_{\2}", text)

    # 点名序列常被 OCR 识别为 ``Qn-1``、``Pn+1`` 或 ``P_n+1``。
    text = re.sub(
        r"(?<![A-Za-z])([PQ])\s*_\s*\{\s*([nmk0-9]+)\s*([+\-])\s*(\d+)\s*\}",
        lambda match: f"{match.group(1)}_{{{match.group(2)}{match.group(3)}{match.group(4)}}}",
        text,
    )
    text = re.sub(
        r"(?<![A-Za-z])([PQ])\s*_\s*([nmk0-9]+)\s*([+\-])\s*(\d+)",
        lambda match: f"{match.group(1)}_{{{match.group(2)}{match.group(3)}{match.group(4)}}}",
        text,
    )
    text = re.sub(
        r"(?<![A-Za-z])([PQ])\s*([nmk])\s*([+\-])\s*(\d+)(?![A-Za-z0-9])",
        lambda match: f"{match.group(1)}_{{{match.group(2)}{match.group(3)}{match.group(4)}}}",
        text,
    )
    text = re.sub(
        r"(?<![A-Za-z])([PQ])\s*_\s*([nmk0-9])(?![A-Za-z0-9])",
        r"\1_\2",
        text,
    )
    text = re.sub(
        r"(?<![A-Za-z])([PQ])\s*([nmk])(?![A-Za-z0-9])",
        r"\1_\2",
        text,
    )
    return re.sub(
        r"(?<![A-Za-z])([PQ])\s*(\d+)(?![A-Za-z0-9])",
        r"\1_\2",
        text,
    )


def _looks_like_math(value: str) -> bool:
    compact = value.strip()
    if not compact or compact in {"()", "{}"}:
        return False
    if re.fullmatch(r"\(?\d+\)?", compact):
        return False
    return bool(
        "\\" in compact
        or re.search(r"[_^<>=+\-]", compact)
        or re.fullmatch(r"[A-Za-z]", compact)
        or re.fullmatch(r"[A-Z](?:[A-Z0-9]|')+", compact)
        or re.search(r"[A-Za-z][A-Za-z0-9_{}^]*\(", compact)
    )


def _wrap_math_runs(text: str) -> str:
    def wrap_part(part: str) -> str:
        def replace(match: re.Match[str]) -> str:
            value = match.group(0)
            stripped = value.strip()
            if not _looks_like_math(stripped):
                return value
            stripped = re.sub(r"[ \t]*([,_<>=+\-])[ \t]*", r"\1", stripped)
            stripped = re.sub(r"}[ \t]+{", "}{", stripped)
            stripped = re.sub(r"\{[ \t]+", "{", stripped)
            stripped = re.sub(r"[ \t]+\}", "}", stripped)
            stripped = re.sub(r"[ \t]+", " ", stripped)
            stripped = re.sub(
                r"(?<=[0-9A-Za-z}])[ \t]+(?=[A-Za-z](?:[_^]|\b))",
                "",
                stripped,
            )
            stripped = re.sub(
                r"(?<=[A-Za-z0-9}])[ \t]+(?=\\(?:left|right)\b)",
                "",
                stripped,
            )
            stripped = _separate_geometry_commands(stripped)
            stripped = re.sub(
                r"\\(ge|le|ne)(?![A-Za-z])[ \t]*",
                r"\\\1 ",
                stripped,
            )
            prefix = value[: len(value) - len(value.lstrip())]
            suffix = value[len(value.rstrip()):]
            return f"{prefix}${stripped}${suffix}"

        return _MATH_RUN.sub(replace, part)

    parts = _DELIMITED_MATH.split(text)
    return "".join(part if part.startswith("$") else wrap_part(part) for part in parts)


def format_math_ocr_text(raw_text: str) -> str:
    """把厂商 OCR 原文整理为适合题目卡片展示的 Markdown + LaTeX。"""
    if not raw_text:
        return ""

    text = raw_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(rf"(?<=[{_CJK}])[ \t]+(?=[{_CJK}])", "", text)
    text = re.sub(r"(?<=概率为)[ \t]+P(?=[ \t]*(?:\\left|\(|（|，|,))", "p", text)
    text = re.sub(
        r"\([ \t]*0[ \t]*[，,][ \t]*\+[ \t]*∞[ \t]*\)",
        r"\\left(0,+\\infty\\right)",
        text,
    )
    text = re.sub(
        r"\\left\((.*?)\\right\)",
        lambda m: "\\left(" + m.group(1).replace("，", ",") + "\\right)",
        text,
    )
    text = text.replace("∞", r"\infty")
    text = text.replace("≥", r"\ge ").replace("≤", r"\le ").replace("≠", r"\ne ")
    text = _repair_geometry_latex(text)
    text = _repair_malformed_math_delimiters(text)
    text = _repair_triangle_vertices(text)
    text = _repair_scalable_delimiters(text)
    text = _compact_latex(text)
    text = _repair_sequence_subscripts(text)
    text = re.sub(r"([A-Za-z]\\?\([^()\n]*\))[ \t]*\)", r"\1", text)
    text = re.sub(r"\.[ \t]*\.(?=[ \t]*[\u3400-\u9fff])", ".", text)
    text = re.sub(r"([①-⑳])(?:[ \t\n]*\1)+", r"\1", text)

    # “概率为 p(范围)”是 OCR 常见连写，改成中文括注可避免被误读为乘法。
    text = re.sub(
        r"(概率为)[ \t]*p[ \t]*\\left\((.*?)\\right\)",
        lambda m: f"{m.group(1)}p（{m.group(2).strip()}）",
        text,
    )
    text = re.sub(r"\(([^()\n]*[\u3400-\u9fff][^()\n]*)\)", r"（\1）", text)

    text = re.sub(r"[ \t]*([，。；：！？、])[ \t]*", r"\1", text)
    text = re.sub(r"([，。；：！？、])(?:\1)+", r"\1", text)
    text = re.sub(r"(?:，[ \t]*){2,}", "，", text)
    text = re.sub(r"(?:。[ \t]*){2,}", "。", text)
    text = re.sub(
        rf"(?<=[{_CJK}])\.(?=[ \t\n]*(?:[{_CJK}]|\([1-9]\d*\)|[①-⑳]|$))",
        "。",
        text,
    )
    text = re.sub(
        rf"(?<=[A-Za-z0-9}})\]])\.(?=[ \t\n]*(?:[{_CJK}]|\([1-9]\d*\)|[①-⑳]|$))",
        "。",
        text,
    )
    text = re.sub(
        rf"(?<=[A-Za-z0-9}})\]])[ \t]+\.(?=[ \t\n]*(?:[{_CJK}]|\([1-9]\d*\)|[①-⑳]|$))",
        "。",
        text,
    )
    text = re.sub(r"[ \t]*(?=\([1-9]\d*\))", "\n", text)
    text = re.sub(r"\(([1-9]\d*)\)[ \t]*", r"(\1) ", text)
    text = re.sub(r"(?<!\n)[ \t]*(?=[①-⑳])", "\n", text)
    text = re.sub(r"([①-⑳])[ \t]*", r"\1 ", text)
    text = re.sub(r"[.。；][ \t]*\n+(?=①)", "：\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    text = _wrap_math_runs(text)
    text = re.sub(rf"(?<=[{_CJK}])[ \t]+(?=\$)", "", text)
    text = re.sub(rf"(?<=\$)[ \t]+(?=[{_CJK}，。；：！？、（])", "", text)
    text = _repair_redundant_inline_dollars(text)
    text = _close_unmatched_inline_math(text)
    return text.strip()
