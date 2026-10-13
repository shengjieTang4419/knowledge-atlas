"""L2 · 检索层：由关键词找「可信源」。

## 可信源是两层的（2026-10-12 定）
- **可信源 = 平台级**：泛化、跨主题复用（GitHub / arXiv / Oracle 官方文档）；
- **条目 = 文件级**：`SourceEntry`，挂在这个主题的模块下（arXiv 上哪篇论文、GitHub 上哪个仓库）。

为什么必须拆：平台是跨主题成立的「出处」事实，具体文件才是零散的。混成一层，搜十个主题就攒出
几十条「可信源」，没有一条可复用——等于没有。收敛不指望模型自觉：`normalize_platforms` 按
**宿主域名**归一（同一个站无论名字怎么写都只算一个平台），模型只负责提条目。

可信度分级（`config/sources.yml`）：规范 · 源码 最高 → 书籍 · 论文 高 → 博客 中 → 社区 低。

## 查找顺序（四级，命中即止）
1. **内置主题模块** `config/sources.yml` 的 `domains` —— 随仓库走的 curated 真相源；
2. **用户模块** `data/settings/settings.json` —— 搜过或手工建的模块（按 topic 匹配）；
3. **AI 判定并自动收录** —— 前两级都没有时，让模型按 `prompts/sourcing.md` 提候选：
   平台补进全局注册表，条目落成一个 `origin=auto` 的模块（下次同主题直接命中，不再烧 token）；
4. 都没有 → `matched=False, needsConfig=True`，界面提示去配置。

每次搜索（第 4 级也算）另记一条**搜索历史**，供侧栏回看；`draft` 预演传 `record_history=False`
保持零副作用。
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app import settings
from app.config import ROOT, load_sources
from app.llm import chat_json, is_online
from app.models import Source, SourceEntry, SourceType
from app.settings import TrustedModule

__all__ = [
    "auto_collect",
    "find_sources",
    "normalize_platforms",
    "rank_sources",
    "search_topic",
    "sort_entries",
]

_SOURCING_PROMPT = ROOT / "prompts" / "sourcing.md"

# 平台归一时类型不明时的兜底档：取最低可信度，宁可不让它排到前面（用户可在设置页改）
_FALLBACK_TYPE: SourceType = "博客"


def _credibility() -> dict[str, int]:
    data = load_sources()
    table = data.get("credibility") or {}
    return {str(k): int(v) for k, v in table.items()}


def rank_sources(sources: list[Source], limit: int = 5) -> list[Source]:
    """按可信度降序；同级保持原序（稳定）。"""
    table = _credibility()
    indexed = list(enumerate(sources))
    indexed.sort(key=lambda pair: (-table.get(pair[1].type, 0), pair[0]))
    return [s for _, s in indexed[:limit]]


def sort_entries(entries: list[SourceEntry], platforms: list[Source]) -> list[SourceEntry]:
    """条目跟着所属平台的可信度排（平台未知的排最后，原序稳定）。"""
    table = _credibility()
    type_of = {p.id: p.type for p in platforms}
    order = {p.id: i for i, p in enumerate(platforms)}
    return sorted(
        entries,
        key=lambda e: (-table.get(type_of.get(e.source, _FALLBACK_TYPE), 0), order.get(e.source, 99)),
    )


def normalize_platforms(
    platforms: list[Source], entries: list[SourceEntry]
) -> tuple[list[Source], list[SourceEntry]]:
    """按 id 归并平台，并把每条条目的 `source` 解析成平台 id。

    解析顺序：平台 id → 平台名 → 条目 locator 的宿主域名。
    都对不上时**兜底建平台**（域名当名字、类型取最低档）——宁可留一条可改的兜底，也不丢条目；
    连域名都没有的条目才丢弃（既无平台又无出处，挂不上任何东西）。

    返回的平台**只留有条目支撑的那些**：没有条目的平台是纯噪声，正是拆两层要消掉的东西。
    """
    by_id: dict[str, Source] = {}
    for src in platforms:
        if not src.id:
            src.id = settings.platform_id(src.name, src.home)
        if not src.id:
            continue
        prev = by_id.get(src.id)
        if prev is None:
            by_id[src.id] = src
            continue
        # 同一个平台的重复项：补空字段，类型取更可信的那个
        prev.why = prev.why or src.why
        prev.home = prev.home or src.home
        if _credibility().get(src.type, 0) > _credibility().get(prev.type, 0):
            prev.type = src.type

    by_name = {settings.fold(s.name): s.id for s in by_id.values()}
    by_host = {settings.host_of(s.home): s.id for s in by_id.values() if settings.host_of(s.home)}

    out: list[SourceEntry] = []
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        raw = entry.source.strip()
        host = settings.host_of(entry.locator)
        sid = raw if raw in by_id else by_name.get(settings.fold(raw), "") or by_host.get(host, "")
        if not sid:
            sid = host or settings.fold(raw)
        if not sid:
            continue
        if sid not in by_id:
            by_id[sid] = Source(
                name=host or raw or sid, type=_FALLBACK_TYPE, home=host, id=sid, origin="auto"
            )
            by_name[settings.fold(by_id[sid].name)] = sid
            if host:
                by_host[host] = sid
        key = (entry.title, entry.locator)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            SourceEntry(title=entry.title, source=sid, locator=entry.locator, note=entry.note)
        )
    used = {e.source for e in out}
    return [p for p in by_id.values() if p.id in used], out


# ---------- 第 1 级：内置主题模块 ----------


def _from_registry(keywords: list[str]) -> tuple[list[Source], list[SourceEntry]]:
    """命中内置主题模块：关键词落在 topic / 平台名 / 条目标题里才算命中。

    ⚠ 不能用 `block_topic in str(block)` 之类自匹配——str(block) 含 topic 本身，
    条件恒为真，会导致任何主题都命中第一个域（实测：搜「Rust 所有权」返回 Java 的源）。
    匹配口径统一走 `settings.matches_keywords`（ASCII 整词 / 中文子串），别各写一套。
    """
    data = load_sources()
    known: dict[str, Source] = {}
    for raw in data.get("platforms") or []:
        src = settings.parse_source(raw)
        if src is not None and src.id:
            known.setdefault(src.id, src)

    platforms: list[Source] = []
    entries: list[SourceEntry] = []
    seen_platforms: set[str] = set()
    for block in (data.get("domains") or {}).values():
        topic = str(block.get("topic", ""))
        raw_items = [x for x in (block.get("items") or []) if isinstance(x, dict)]
        block_entries = [e for e in (settings.parse_entry(x) for x in raw_items) if e is not None]
        names = [known[e.source].name for e in block_entries if e.source in known]
        if not settings.matches_keywords(keywords, [topic, *names, *(e.title for e in block_entries)]):
            continue
        for entry in block_entries:
            platform = known.get(entry.source)
            if platform is not None and platform.id not in seen_platforms:
                seen_platforms.add(platform.id)
                platforms.append(platform)
            entries.append(entry)
    return platforms, entries


# ---------- 第 2 级：用户模块 ----------


def _module_content(mods: list[settings.TrustedModule]) -> tuple[list[Source], list[SourceEntry]]:
    """模块集合 → (平台清单, 条目清单)。

    条目按 (标题, 定位) 去重；平台从注册表取（按 id 或名字命中），注册表里缺的由
    `normalize_platforms` 按域名兜底补——引用悬空时宁可现补一个，也不能让整次搜索白跑。
    """
    entries: list[SourceEntry] = []
    seen: set[tuple[str, str]] = set()
    for mod in mods:
        for entry in mod.items:
            key = (entry.title, entry.locator)
            if key in seen:
                continue
            seen.add(key)
            entries.append(entry)
    wanted = {settings.fold(e.source) for e in entries if e.source}
    candidates = [
        s for s in settings.load_platforms() if s.id in wanted or settings.fold(s.name) in wanted
    ]
    return normalize_platforms(candidates, entries)


def _from_user_modules(
    keywords: list[str],
) -> tuple[list[Source], list[SourceEntry], settings.TrustedModule | None]:
    """命中用户模块；返回 (平台清单, 条目清单, 命中的首个模块)。"""
    hits = settings.match_modules(keywords)
    if not hits:
        return [], [], None
    platforms, entries = _module_content(hits)
    return platforms, entries, hits[0]


# ---------- 第 3 级：AI 判定并自动收录 ----------


@lru_cache(maxsize=1)
def _sourcing_system_prompt() -> str:
    """复用 prompts/sourcing.md 里的判据（prompt 是资产，单一真相源在文件里）。"""
    try:
        return _SOURCING_PROMPT.read_text(encoding="utf-8")
    except OSError:
        return "你是可信源检索器。为学习主题找相对可信的来源。"


def _llm_sources(topic: str, keywords: list[str]) -> tuple[list[Source], list[SourceEntry]]:
    """让模型按 sourcing.md 的判据提「平台 + 条目」两层候选。"""
    data = chat_json(
        _sourcing_system_prompt(),
        f"主题：{topic}\n检索关键词：{'、'.join(keywords)}\n"
        '只输出 JSON：{"sources":[{"name":"平台名（如 GitHub / arXiv / Oracle 官方文档）",'
        '"type":"规范|源码|书籍|论文|博客|社区","why":"","home":"平台入口 URL"}],'
        '"items":[{"title":"具体文件/页面/章节","source":"所属平台的 name（与上面一致）",'
        '"locator":"","note":""}]}',
    )
    platforms = [s for s in (settings.parse_source(x) for x in data.get("sources") or []) if s]
    entries = [e for e in (settings.parse_entry(x) for x in data.get("items") or []) if e]
    return platforms, entries


def auto_collect(
    topic: str, keywords: list[str], limit: int = 5
) -> tuple[list[Source], list[SourceEntry]]:
    """AI 判定 → 平台补进全局注册表 + **自动收录成一个 auto 模块**；返回收录后的两层内容。

    收录条件保守：模型必须同时给出平台与条目；否则不落盘（不污染设置）。
    """
    platforms, entries = normalize_platforms(*_llm_sources(topic, keywords))
    if not platforms or not entries:
        return [], []
    platforms = rank_sources(platforms, limit=limit)
    keep = {p.id for p in platforms}
    entries = [e for e in entries if e.source in keep]
    settings.register_platforms(platforms)
    settings.upsert_module(
        TrustedModule(
            id=settings.module_id(topic),
            topic=topic,
            origin="auto",
            keywords=list(keywords),
            items=entries,
        )
    )
    return platforms, entries


# ---------- 对外 ----------


def find_sources(keywords: list[str], limit: int = 5) -> list[Source]:
    """关键词 → 可信源清单（平台级，≤limit，宁缺勿滥）。内置 → 用户模块 → 空。

    L3/L4 依赖它的只有「有哪些可信源」这一件事（条目留在 L2 模块里）。
    """
    if not keywords:
        return []
    platforms, _entries = _from_registry(keywords)
    if not platforms:
        platforms, _entries, _mod = _from_user_modules(keywords)
    return rank_sources(platforms, limit=limit)


def search_topic(
    topic: str, limit: int = 5, *, allow_auto: bool = True, record_history: bool = True
) -> dict[str, Any]:
    """L1 + L2 编排：主题 → 关键词 → 可信源（平台）+ 条目；必要时 AI 判定并自动收录。

    返回结构供界面直接用。字段口径：
    - `origin`     —— builtin | auto | manual（平台与条目共用同一来路）
    - `matched`    —— 是否拿到可信源
    - `needsConfig`—— 没拿到 → 界面提示去配置
    - `autoCollected` —— 本次是否**新收录**了模块（界面提示「已收录到设置」）
    - `moduleId`   —— 命中的模块 id（便于界面跳到设置页定位）
    - `llmAvailable` —— 是否具备 AI 判定条件（无 key 时界面解释「为什么没自动生成」）
    - `record_history=False` —— 预演（`draft`）用：零副作用

    缓存命中时**连 L1 拆词也省掉**：模块里存着当初的关键词，重搜同一主题不该再调一次模型
    （否则「下次直接命中、不再调模型」只是句空话）。
    """
    from app.layers.topic import orient  # 延迟导入，避免 layers 之间循环

    topic = (topic or "").strip()
    module_count = len(settings.load_modules())
    if not topic:
        return _result("", [], [], [], "", "", False, module_count)

    module = settings.find_module(topic)
    keywords = list(module.keywords) if module is not None and module.keywords else orient(topic)

    # 1) 内置
    platforms, entries = _from_registry(keywords)
    origin, mid, auto_collected = "builtin", "", False

    # 2) 用户模块（= 之前搜过或手工建过的，模块即缓存，缓存键就是 topic）
    if not platforms:
        if module is not None:
            platforms, entries = _module_content([module])
        else:
            platforms, entries, module = _from_user_modules(keywords)
        if platforms:
            origin = module.origin if module else "manual"
            mid = module.id if module else ""

    # 3) AI 判定并自动收录
    if not platforms and allow_auto and is_online():
        auto_platforms, auto_entries = auto_collect(topic, keywords, limit=limit)
        if auto_platforms:
            platforms, entries = auto_platforms, auto_entries
            origin, auto_collected = "auto", True
            mid = settings.module_id(topic)
            module_count = len(settings.load_modules())

    # 4) 截断与排序：平台≤limit，条目只留被收纳平台的
    platforms = rank_sources(platforms, limit=limit)
    keep = {p.id for p in platforms}
    entries = sort_entries([e for e in entries if e.source in keep], platforms)

    payload = _result(
        topic, keywords, platforms, entries, origin, mid, auto_collected, module_count
    )
    if record_history:
        settings.record_search(topic, bool(platforms), len(platforms))
    return payload


def _result(
    topic: str,
    keywords: list[str],
    sources: list[Source],
    items: list[SourceEntry],
    origin: str,
    module_id: str,
    auto_collected: bool,
    module_count: int,
) -> dict[str, Any]:
    return {
        "topic": topic,
        "keywords": keywords,
        "sources": [{**s.to_dict(), "origin": origin} for s in sources],
        "items": [e.to_dict() for e in items],
        "matched": bool(sources),
        # 空主题没什么可配的（不是「没找到」），别引导用户去设置页
        "needsConfig": not sources and bool(topic),
        "autoCollected": auto_collected,
        "moduleId": module_id,
        "moduleCount": module_count,
        # 离线（没配 LLM key）时界面据此解释「为什么没自动生成」
        "llmAvailable": is_online(),
    }
