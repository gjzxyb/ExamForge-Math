"""数学试题 OCR 文本的保守清洗与 LaTeX 排版。"""

from __future__ import annotations

import re


_CJK = r"\u3400-\u4dbf\u4e00-\u9fff"
_MATH_RUN = re.compile(
    r"(?:\\[A-Za-z]+|[A-Za-z0-9_{}^+\-<>=()])"
    r"(?:[ \t]*(?:\\[A-Za-z]+|[A-Za-z0-9_{}^+\-<>=()]))*"
)
_DELIMITED_MATH = re.compile(r"(\$\$.*?\$\$|\$.*?\$)", re.DOTALL)


def _compact_braced_arg(match: re.Match[str]) -> str:
    command, value = match.group(1), match.group(2)
    return f"\\{command}{{{''.join(value.split())}}}"


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
    return re.sub(r"(?<![A-Za-z])([pq])\s*(\d+)\b", r"\1_{\2}", text)


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
        or re.search(r"[A-Za-z][A-Za-z0-9_{}^]*\(", compact)
    )


def _wrap_math_runs(text: str) -> str:
    def wrap_part(part: str) -> str:
        def replace(match: re.Match[str]) -> str:
            value = match.group(0)
            stripped = value.strip()
            if not _looks_like_math(stripped):
                return value
            stripped = re.sub(r"[ \t]*([_<>=+\-])[ \t]*", r"\1", stripped)
            stripped = re.sub(r"}[ \t]+{", "}{", stripped)
            stripped = re.sub(r"\{[ \t]+", "{", stripped)
            stripped = re.sub(r"[ \t]+\}", "}", stripped)
            stripped = re.sub(r"[ \t]+", " ", stripped)
            stripped = re.sub(r"\\(ge|le|ne)[ \t]*", r"\\\1 ", stripped)
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
    text = text.replace("≥", r"\ge ").replace("≤", r"\le ").replace("≠", r"\ne ")
    text = _compact_latex(text)
    text = _repair_sequence_subscripts(text)

    # “概率为 p(范围)”是 OCR 常见连写，改成中文括注可避免被误读为乘法。
    text = re.sub(
        r"(概率为)[ \t]*p[ \t]*\\left\((.*?)\\right\)",
        lambda m: f"{m.group(1)}p（{m.group(2).strip()}）",
        text,
    )
    text = re.sub(r"\(([^()\n]*[\u3400-\u9fff][^()\n]*)\)", r"（\1）", text)

    text = re.sub(r"[ \t]*([，。；：！？、])[ \t]*", r"\1", text)
    text = re.sub(r"(?:，[ \t]*){2,}", "，", text)
    text = re.sub(r"(?:。[ \t]*){2,}", "。", text)
    text = re.sub(
        rf"(?<=[{_CJK}])\.(?=[ \t]*(?:[{_CJK}]|\([1-9]\d*\)|$))",
        "。",
        text,
    )
    text = re.sub(r"[ \t]*(?=\([1-9]\d*\))", "\n", text)
    text = re.sub(r"\(([1-9]\d*)\)[ \t]*", r"(\1) ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    text = _wrap_math_runs(text)
    text = re.sub(rf"(?<=[{_CJK}])[ \t]+(?=\$)", "", text)
    text = re.sub(rf"(?<=\$)[ \t]+(?=[{_CJK}，。；：！？、（])", "", text)
    return text.strip()
