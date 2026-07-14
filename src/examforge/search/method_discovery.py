"""全网搜索发现解题方法。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

from ..config.settings import WebSearchSettings
from ..models import SubjectArea


@dataclass
class SearchHit:
    title: str
    snippet: str
    url: str = ""


@dataclass
class MethodCandidate:
    name: str
    subject_area: SubjectArea
    applicability: str
    core_idea: str
    key_theorem: str = ""
    secondary_theorems: str = ""
    procedure_steps: str = ""
    pitfalls: str = ""
    source_title: str = ""
    source_url: str = ""


class WebSearchError(RuntimeError):
    pass


MOCK_HITS = [
    SearchHit(
        title="高中导数压轴题：隐零点法与同构构造函数法",
        snippet="总结隐零点法、同构构造函数法在含参不等式、零点个数与最值问题中的适用条件和常见误区。",
        url="https://example.com/implicit-zero-method",
    ),
    SearchHit(
        title="圆锥曲线设而不求与韦达定理模型",
        snippet="解析设而不求法、点差法、韦达定理模型在弦长、面积、定点定值问题中的通用步骤。",
        url="https://example.com/conic-vieta-model",
    ),
    SearchHit(
        title="高中数学压轴题切线放缩法与泰勒近似思想",
        snippet="切线放缩法适合指数、对数、三角函数不等式证明，需要核对放缩方向、等号条件和变量区间。",
        url="https://example.com/tangent-bound",
    ),
]


METHOD_PATTERN = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9·]{2,24}(?:法|模型|策略|技巧|思想|定理|结论))")


def search_method_pages(query: str, settings: WebSearchSettings, *, max_results: int = 5) -> list[SearchHit]:
    """调用配置的搜索 API,返回网页命中。"""
    provider = (settings.provider or "disabled").lower()
    if provider == "disabled":
        raise WebSearchError("全网搜索 API 未启用，请在设置中配置搜索 Provider。")
    if provider == "mock":
        q = query.strip()
        if not q:
            return MOCK_HITS[:max_results]
        words = [w for w in re.split(r"\s+", q) if w]
        ranked = sorted(
            MOCK_HITS,
            key=lambda h: -sum(1 for w in words if w in h.title or w in h.snippet),
        )
        return ranked[:max_results]
    endpoint = settings.endpoint or ("https://serpapi.com/search.json" if provider == "serpapi" else "")
    if not endpoint:
        raise WebSearchError("搜索 Endpoint 为空，请先在设置中填写 API 地址。")

    try:
        with httpx.Client(timeout=settings.timeout) as client:
            if provider == "serpapi":
                resp = client.get(endpoint, params={
                    "q": query,
                    "api_key": settings.api_key,
                    "engine": "google",
                    "num": max_results,
                    "hl": "zh-cn",
                })
            elif provider == "bing":
                resp = client.get(endpoint, params={"q": query, "count": max_results}, headers={
                    "Ocp-Apim-Subscription-Key": settings.api_key,
                })
            else:  # custom: 兼容返回 results/items 数组的代理
                headers = {"Authorization": f"Bearer {settings.api_key}"} if settings.api_key else {}
                resp = client.get(endpoint, params={"q": query, "count": max_results}, headers=headers)
        resp.raise_for_status()
        return _hits_from_response(resp.json(), provider=provider)[:max_results]
    except httpx.HTTPError as exc:
        raise WebSearchError(f"搜索 API 调用失败：{exc}") from exc
    except Exception as exc:
        raise WebSearchError(f"搜索结果解析失败：{type(exc).__name__}: {exc}") from exc


def _hits_from_response(data: dict[str, Any], *, provider: str) -> list[SearchHit]:
    rows: list[Any]
    if provider == "bing":
        rows = data.get("webPages", {}).get("value", [])
        return [SearchHit(title=str(r.get("name", "")), snippet=str(r.get("snippet", "")), url=str(r.get("url", ""))) for r in rows]
    rows = data.get("organic_results") or data.get("results") or data.get("items") or []
    hits = []
    for r in rows:
        hits.append(SearchHit(
            title=str(r.get("title") or r.get("name") or ""),
            snippet=str(r.get("snippet") or r.get("summary") or r.get("description") or ""),
            url=str(r.get("link") or r.get("url") or ""),
        ))
    return hits


def discover_method_candidates(
    query: str,
    area: SubjectArea,
    settings: WebSearchSettings,
    *,
    max_results: int = 5,
) -> list[MethodCandidate]:
    hits = search_method_pages(query, settings, max_results=max_results)
    candidates: list[MethodCandidate] = []
    seen: set[str] = set()
    for hit in hits:
        text = f"{hit.title}。{hit.snippet}"
        names = METHOD_PATTERN.findall(text)
        if not names:
            names = [_fallback_name(hit.title)]
        for name in names[:2]:
            name = _clean_name(name)
            if not name or name in seen:
                continue
            seen.add(name)
            candidates.append(_candidate_from_hit(name, area, hit))
            break
    return candidates


def _fallback_name(title: str) -> str:
    cleaned = re.sub(r"[｜|_\-—].*$", "", title).strip()
    cleaned = re.sub(r"(高中数学|高考|压轴题|专题|总结|技巧|大全|例题).*", "", cleaned).strip()
    if not cleaned:
        cleaned = title[:18].strip() or "全网发现方法"
    if not any(cleaned.endswith(x) for x in ("法", "模型", "策略", "思想", "技巧", "定理")):
        cleaned += "方法"
    return cleaned


def _clean_name(name: str) -> str:
    name = re.sub(r"^(?:高中数学|高考|压轴题|数学)", "", name).strip(" ：:，,。；;、")
    return name[:32]


def _candidate_from_hit(name: str, area: SubjectArea, hit: SearchHit) -> MethodCandidate:
    theorem = name if "定理" in name else ""
    secondary = ""
    for m in METHOD_PATTERN.findall(hit.snippet):
        if m != name and ("定理" in m or "结论" in m):
            secondary = m
            break
    source = f"来源：{hit.title} {hit.url}".strip()
    return MethodCandidate(
        name=name,
        subject_area=area,
        applicability=hit.snippet[:180] or f"由全网搜索“{hit.title}”发现，需教研复核后使用。",
        core_idea=(f"全网搜索候选：{hit.title}\n{hit.snippet}\n{source}").strip(),
        key_theorem=theorem,
        secondary_theorems=secondary,
        procedure_steps="1. 阅读来源材料并核对适用条件\n2. 用本库已确认例题验证\n3. 标注反例和边界条件后再提升为 confirmed",
        pitfalls="搜索发现的方法需人工复核；不要仅凭网页标题直接套用。",
        source_title=hit.title,
        source_url=hit.url,
    )
