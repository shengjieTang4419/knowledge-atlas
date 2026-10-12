"""L2 · 检索层：由关键词找「可信源」（可信元）。

可信度分级（`config/sources.yml`）：规范 · 源码 最高 → 书籍 · 论文 高 → 博客 中 → 社区 低。
五问筛：稀缺 / 贴合 / 门槛 / 差分 / 信噪（前两条为硬门槛）。

## 查找顺序（四级，命中即止）
1. **内置模块** `config/sources.yml` 的 `domains` —— 随仓库走的 curated 真相源；
2. **用户模块** `data/settings/settings.json` —— 搜过或手工建的「搜索模块」（按 topic 匹配）；
3. **AI 判定并自动收录** —— 前两级都没有时，让模型按 `prompts/sourcing.md` 的判据提候选，
   **落成一个 `origin=auto` 的模块**（下次同主题直接命中第 2 级，不再烧 token）；
4. 都没有 → `matched=False, needsConfig=True`，界面提示去配置。

## 为什么第 3 级要落盘
「可信源」天生按主题组织，同一个主题第二次搜索没有理由再问一遍模型。
落盘即缓存：第 2 级命中就是它的缓存命中路径。
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from app import settings
from app.config import ROOT, load_sources
from app.llm import chat_json, is_online
from app.models import Source
from app.settings import TrustedModule

__all__ = ["find_sources", "rank_sources", "search_topic"]

_VALID_TYPES = {"规范", "源码", "书籍", "论文", "博客", "社区"}


def _fold(value: str) -> str:
    """匹配用归一：小写 + 去空白。

    实测坑：`"java" in "Java 多线程"` 为 False —— 大小写敏感会让用户打小写
    就查不到内置模块（中文不受影响，但英文技术名词几乎都是混写）。
    """
    return re.sub(r"\s+", "", (value or "").lower())
_SOURCING_PROMPT = ROOT / "prompts" / "sourcing.md"


def _credibility() -> dict[str, int]:
    data = load_sources()
    table = data.get("credibility") or {}
    return {str(k): int(v) for k, v in table.items()}


def _as_source(raw: dict[str, object]) -> Source | None:
    name = str(raw.get("name", "")).strip()
    if not name:
        return None
    stype = str(raw.get("type", "博客")).strip()
    if stype not in _VALID_TYPES:
        stype = "博客"
    return Source(
        name=name,
        type=stype,  # type: ignore[arg-type]
        why=str(raw.get("why", "")).strip(),
        locator=str(raw.get("locator", "")).strip(),
    )


def rank_sources(sources: list[Source], limit: int = 5) -> list[Source]:
    """按可信度降序；同级保持原序（稳定）。"""
    table = _credibility()
    indexed = list(enumerate(sources))
    indexed.sort(key=lambda pair: (-table.get(pair[1].type, 0), pair[0]))
    return [s for _, s in indexed[:limit]]


# ---------- 第 1 级：内置模块 ----------


def _from_registry(keywords: list[str]) -> list[Source]:
    """命中内置领域注册表：关键词落在该域的 topic 或源名里才算命中。

    ⚠ 不能用 `block_topic in str(block)` 之类自匹配——str(block) 含 topic 本身，
    条件恒为真，会导致任何主题都命中第一个域（实测：搜「Rust 所有权」返回 Java 的源）。
    """
    data = load_sources()
    hits: list[Source] = []
    for block in (data.get("domains") or {}).values():
        topic = str(block.get("topic", ""))
        names = " ".join(str(s.get("name", "")) for s in block.get("sources") or [] if isinstance(s, dict))
        haystack = _fold(f"{topic} {names}")
        if not any(k and _fold(k) in haystack for k in keywords):
            continue
        for raw in block.get("sources") or []:
            if isinstance(raw, dict):
                src = _as_source(raw)
                if src:
                    hits.append(src)
    return hits


# ---------- 第 2 级：用户模块 ----------


def _from_user_modules(keywords: list[str]) -> tuple[list[Source], TrustedModule | None]:
    """命中用户模块；返回 (源清单, 命中的首个模块)。"""
    hits = settings.match_modules(keywords)
    if not hits:
        return [], None
    primary = hits[0]
    merged: list[Source] = []
    seen: set[str] = set()
    for m in hits:  # 多个模块命中时合并（少见，但别丢）
        for s in m.sources:
            if s.name not in seen:
                seen.add(s.name)
                merged.append(s)
    return merged, primary


# ---------- 第 3 级：AI 判定并自动收录 ----------


@lru_cache(maxsize=1)
def _sourcing_system_prompt() -> str:
    """复用 prompts/sourcing.md 里的判据（prompt 是资产，单一真相源在文件里）。"""
    try:
        return _SOURCING_PROMPT.read_text(encoding="utf-8")
    except OSError:
        return "你是可信源检索器。为学习主题找相对可信的来源。"


def _llm_sources(topic: str, keywords: list[str]) -> list[Source]:
    """让模型按 sourcing.md 的判据提候选。"""
    data = chat_json(
        _sourcing_system_prompt(),
        f"主题：{topic}\n检索关键词：{'、'.join(keywords)}\n"
        '只输出 JSON：{"sources":[{"name":"","type":"规范|源码|书籍|论文|博客|社区",'
        '"why":"","locator":""}]}',
    )
    out: list[Source] = []
    for raw in data.get("sources") or []:
        if isinstance(raw, dict):
            src = _as_source(raw)
            if src:
                out.append(src)
    return out


def auto_collect(topic: str, keywords: list[str], limit: int = 5) -> list[Source]:
    """AI 判定 → **自动收录成一个 auto 模块**；返回收录后的源（可能为空）。

    收录条件保守：模型必须给出至少一条合法源；否则不落盘（不污染设置）。
    """
    sources = _llm_sources(topic, keywords)
    if not sources:
        return []
    ranked = rank_sources(sources, limit=limit)
    settings.upsert_module(
        TrustedModule(
            id=settings.module_id(topic),
            topic=topic,
            origin="auto",
            keywords=list(keywords),
            sources=ranked,
        )
    )
    return ranked


# ---------- 对外 ----------


def find_sources(keywords: list[str], limit: int = 5) -> list[Source]:
    """关键词 → 可信源清单（≤limit，宁缺勿滥）。内置 → 用户模块 → 空。"""
    if not keywords:
        return []
    found = _from_registry(keywords)
    if not found:
        found, _mod = _from_user_modules(keywords)
    return rank_sources(found, limit=limit)


def search_topic(topic: str, limit: int = 5, *, allow_auto: bool = True) -> dict[str, Any]:
    """L1 + L2 编排：主题 → 关键词 → 可信源；必要时 AI 判定并自动收录。

    返回结构供界面直接用。字段口径：
    - `origin`     —— builtin | auto | manual | llm（llm = 生成了但没落盘，不该出现）
    - `matched`    —— 是否拿到可信源
    - `needsConfig`—— 没拿到 → 界面提示去配置
    - `autoCollected` —— 本次是否**新收录**了模块（界面提示「已收录到设置」）
    - `moduleId`   —— 命中的模块 id（便于界面跳到设置页定位）
    - `llmAvailable` —— 是否具备 AI 判定条件（无 key 时界面解释「为什么没自动生成」）
    """
    from app.layers.topic import orient  # 延迟导入，避免 layers 之间循环

    topic = (topic or "").strip()
    module_count = len(settings.load_modules())
    if not topic:
        return {
            "topic": "",
            "keywords": [],
            "sources": [],
            "matched": False,
            "needsConfig": False,
            "autoCollected": False,
            "moduleId": "",
            "moduleCount": module_count,
            "llmAvailable": is_online(),
        }

    keywords = orient(topic)

    # 1) 内置
    builtin = _from_registry(keywords)
    if builtin:
        return _result(topic, keywords, rank_sources(builtin, limit), "builtin", "", False, module_count)

    # 2) 用户模块（= 之前搜过或手工建过的）
    user_sources, module = _from_user_modules(keywords)
    if user_sources:
        origin = module.origin if module else "manual"
        return _result(
            topic,
            keywords,
            rank_sources(user_sources, limit),
            origin,
            module.id if module else "",
            False,
            module_count,
        )

    # 3) AI 判定并自动收录
    if allow_auto and is_online():
        auto = auto_collect(topic, keywords, limit=limit)
        if auto:
            return _result(
                topic,
                keywords,
                auto,
                "auto",
                settings.module_id(topic),
                True,
                len(settings.load_modules()),
            )

    # 4) 都没有 → 提示去配置
    return _result(topic, keywords, [], "", "", False, module_count)


def _result(
    topic: str,
    keywords: list[str],
    sources: list[Source],
    origin: str,
    module_id: str,
    auto_collected: bool,
    module_count: int,
) -> dict[str, Any]:
    return {
        "topic": topic,
        "keywords": keywords,
        "sources": [
            {"name": s.name, "type": s.type, "why": s.why, "locator": s.locator, "origin": origin}
            for s in sources
        ],
        "matched": bool(sources),
        "needsConfig": not sources,
        "autoCollected": auto_collected,
        "moduleId": module_id,
        "moduleCount": module_count,
        # 离线（没配 LLM key）时界面据此解释「为什么没自动生成」
        "llmAvailable": is_online(),
    }
