"""用户设置（运行时状态，不入 git）。

存放 `data/settings/settings.json`。与 `config/*.yml` 的分工：
- `config/sources.yml` = 随仓库走的**内置可信源（平台）** + **内置主题模块**（curated 真相源）；
- 这里 = 用户侧的**平台注册表** + **搜索模块** + **搜索历史**。

## 可信源是两层的（2026-10-12 定）
- **可信源 = 平台级**：泛化、跨主题复用（GitHub / arXiv / Oracle 官方文档）。全局一份，不按主题复制；
- **条目** = 某平台上具体哪个文件/页面（`SourceEntry`），挂在主题模块下。

为什么拆开：平台是跨主题成立的「出处」事实，具体文件才是零散的。混成一层的话，搜十个主题就攒出
几十条「可信源」，没有一条可复用——等于没有。收敛靠 `retrieve.normalize_platforms`（宿主域名归一），
不指望模型自觉。

## 什么是「搜索模块」
一个模块 = 一个 topic 的**条目集合**（不是平台本身）：

    {id: "java多线程·内存可见性", topic: "Java 多线程 · 内存可见性",
     keywords: [...], origin: "auto", items: [{title, source, locator, note}]}

`origin` 区分来路：`auto`（搜主题时 AI 判定后自动收录，下次同 topic 直接命中，不再烧 token）/
`manual`（设置页手工建或改过）。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.config import DATA, load_sources
from app.models import Source, SourceEntry

__all__ = [
    "HISTORY_LIMIT",
    "LLM_CONFIG_PATH",
    "LLM_CHAIN_MODES",
    "HistoryItem",
    "LlmChain",
    "LlmConfig",
    "LlmProvider",
    "SETTINGS_PATH",
    "TrustedModule",
    "add_module_item",
    "clear_history",
    "delete_module",
    "find_module",
    "fold",
    "host_of",
    "llm_config_payload",
    "load_history",
    "load_llm_config",
    "load_modules",
    "load_platforms",
    "load_settings",
    "load_user_platforms",
    "match_modules",
    "matches_keywords",
    "module_id",
    "parse_entry",
    "parse_source",
    "platform_id",
    "record_search",
    "register_platforms",
    "remove_module_item",
    "remove_platform",
    "save_llm_config_payload",
    "save_settings",
    "upsert_module",
]

SETTINGS_DIR = DATA / "settings"
SETTINGS_PATH = SETTINGS_DIR / "settings.json"
TZ = ZoneInfo("Asia/Shanghai")

VALID_TYPES: tuple[str, ...] = ("规范", "源码", "书籍", "论文", "博客", "社区")
ORIGINS: tuple[str, ...] = ("auto", "manual")
PLATFORM_ORIGINS: tuple[str, ...] = ("builtin", "auto", "manual")

# 侧栏就一列，「我搜过什么」留太多反而找不着
HISTORY_LIMIT = 20

_URL_RE = re.compile(r"https?://([^\s/，,；;）)】\]]+)", re.IGNORECASE)


@dataclass
class TrustedModule:
    """一个搜索模块：某 topic 的**可信源条目**集合（平台本身在全局注册表里）。"""

    id: str
    topic: str
    origin: str = "manual"  # auto | manual
    keywords: list[str] = field(default_factory=list)
    items: list[SourceEntry] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def platform_ids(self) -> list[str]:
        """模块实际引用到的平台 id（去重保序）——按条目派生，不另存一份免得两处不一致。"""
        seen: dict[str, None] = {}
        for entry in self.items:
            if entry.source:
                seen.setdefault(entry.source, None)
        return list(seen)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "origin": self.origin,
            "keywords": list(self.keywords),
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "items": [e.to_dict() for e in self.items],
        }


@dataclass
class HistoryItem:
    """一条搜索历史（持久化，侧栏「搜索」下方展示）。"""

    topic: str
    at: str = ""
    matched: bool = False
    source_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "at": self.at,
            "matched": self.matched,
            "sourceCount": self.source_count,
        }


def module_id(topic: str) -> str:
    """由 topic 派生稳定 id：同一主题只有一个模块（重复搜索即更新，不新增）。

    同时是**搜索历史的去重键**：搜过的主题再搜一次只是把它顶到最前，不新增一条。
    """
    return re.sub(r"\s+", "", (topic or "").strip()).lower()


def _now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def fold(value: str) -> str:
    """匹配 / id 归一：小写 + 去空白（大小写不敏感）。"""
    return re.sub(r"\s+", "", (value or "").lower())


def host_of(value: str) -> str:
    """从任意文本里抽宿主域名（取第一个 URL，去 `www.`，小写）；抽不到返回空串。"""
    match = _URL_RE.search(value or "")
    if not match:
        return ""
    host = match.group(1).strip().lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def platform_id(name: str, home: str = "") -> str:
    """平台归一 id：**宿主域名优先**——同一个站（github.com）名字怎么写都只算一个平台。

    没有 URL 的来源（ISBN、课程名）退化为名字归一；这样库里平台数只由「站」的个数决定，
    不由「被搜过多少次」决定。
    """
    return host_of(home) or host_of(name) or fold(name)


def parse_source(raw: object) -> Source | None:
    """dict → Source（平台级）。名字必填；类型非法兜底「博客」；id 未给则按 home 归一。"""
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name", "")).strip()
    if not name:
        return None
    stype = str(raw.get("type", "博客")).strip()
    if stype not in VALID_TYPES:
        stype = "博客"
    origin = str(raw.get("origin", "manual")).strip()
    if origin not in PLATFORM_ORIGINS:
        origin = "manual"
    # 旧字段 `locator` = 平台入口（拆两层前的写法），读时兼容，写时只写 `home`
    home = str(raw.get("home") or raw.get("locator") or "").strip()
    return Source(
        name=name,
        type=stype,  # type: ignore[arg-type]  # 值已校验 ∈ VALID_TYPES，mypy 收窄不了 str→Literal
        why=str(raw.get("why", "")).strip(),
        home=home,
        id=str(raw.get("id", "")).strip() or platform_id(name, home),
        origin=origin,
    )


def parse_entry(raw: object) -> SourceEntry | None:
    """dict → SourceEntry（条目）。标题必填。"""
    if not isinstance(raw, dict):
        return None
    title = str(raw.get("title", "")).strip()
    if not title:
        return None
    return SourceEntry(
        title=title,
        source=str(raw.get("source", "")).strip(),
        locator=str(raw.get("locator", "")).strip(),
        note=str(raw.get("note", "")).strip(),
    )


def _parse_history(raw: object) -> HistoryItem | None:
    if not isinstance(raw, dict):
        return None
    topic = str(raw.get("topic", "")).strip()
    if not topic:
        return None
    return HistoryItem(
        topic=topic,
        at=str(raw.get("at", "")).strip(),
        matched=bool(raw.get("matched")),
        source_count=int(raw.get("sourceCount") or 0),
    )


def _parse_module(raw: object) -> TrustedModule | None:
    if not isinstance(raw, dict):
        return None
    topic = str(raw.get("topic", "")).strip()
    if not topic:
        return None
    origin = str(raw.get("origin", "manual")).strip()
    if origin not in ORIGINS:
        origin = "manual"
    raw_items = raw.get("items") or []
    items = [e for e in (parse_entry(x) for x in raw_items) if e is not None]
    keywords = [str(k).strip() for k in (raw.get("keywords") or []) if str(k).strip()]
    mid = str(raw.get("id", "")).strip() or module_id(topic)
    return TrustedModule(
        id=mid,
        topic=topic,
        origin=origin,
        keywords=keywords,
        items=items,
        created_at=str(raw.get("createdAt", "")),
        updated_at=str(raw.get("updatedAt", "")),
    )


def _migrate(raw: dict[str, Any]) -> dict[str, Any]:
    """旧格式 → 当前格式（幂等、不写盘；下一次写操作自然落成新格式）。

    两种旧格式：
    1. 扁平 `trusted_sources`（最早一版）→ 一个手工模块；
    2. 模块内 `sources`（平台与文件混体）→ 拆成 `items` + 全局平台注册表：
       旧源名当条目标题、旧 locator 当条目定位，同时按 locator 域名建平台——旧库里同一站
       的多条源会当场收敛成一个平台，正是拆两层想要的结果。
    """
    out = dict(raw)
    platforms: list[dict[str, Any]] = [p for p in (out.get("platforms") or []) if isinstance(p, dict)]
    known = {str(p.get("id", "")) for p in platforms}

    if "modules" in raw:
        raw_modules: list[Any] = list(raw.get("modules") or [])
    else:
        legacy = raw.get("trusted_sources") or []
        raw_modules = (
            [{"topic": "手工收录（旧格式迁移）", "origin": "manual", "sources": legacy}] if legacy else []
        )

    modules: list[dict[str, Any]] = []
    for mod in raw_modules:
        if not isinstance(mod, dict):
            continue
        item = dict(mod)
        legacy_sources = item.pop("sources", None)
        if isinstance(legacy_sources, list):
            entries: list[dict[str, Any]] = []
            for raw_source in legacy_sources:
                src = parse_source(raw_source)
                if src is None:
                    continue
                if src.id not in known:
                    known.add(src.id)
                    # 平台名取宿主域名（id 就是它）：旧字段把「哪个文件」当名字，正是要拆掉的那层
                    host = host_of(src.home)
                    platforms.append(
                        {**src.to_dict(), "name": host or src.name, "origin": "manual"}
                    )
                entries.append(
                    SourceEntry(
                        title=src.name, source=src.id, locator=src.home, note=src.why
                    ).to_dict()
                )
            item["items"] = entries
        modules.append(item)

    out["modules"] = modules
    out["platforms"] = platforms
    return out


def _read_raw() -> dict[str, Any]:
    """原始读（不迁移）；文件不存在/损坏时返回空结构（不让界面因缺文件而崩）。"""
    if not SETTINGS_PATH.exists():
        return {}
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return raw if isinstance(raw, dict) else {}


def load_settings() -> dict[str, Any]:
    """读设置（含旧格式迁移）：`modules` / `platforms` / `history` 三段。"""
    return _migrate(_read_raw())


def save_settings(data: dict[str, Any]) -> str:
    """原子写：先写临时文件再替换，避免中断留下半个 JSON。"""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(SETTINGS_PATH)
    return str(SETTINGS_PATH)


def _write_section(key: str, value: list[dict[str, Any]]) -> None:
    """只改一段、其余原样保留（读-改-写）。

    为什么不做「整体覆盖」：模块、平台注册表、历史同住一个文件，谁写谁都得保住另外两段，
    否则改个平台会把搜索历史抹掉。
    """
    raw = _migrate(_read_raw())
    raw[key] = value
    save_settings(raw)


def load_modules() -> list[TrustedModule]:
    """读全部搜索模块（按更新时间倒序：最近用的在前）。"""
    raw = load_settings().get("modules") or []
    mods = [m for m in (_parse_module(x) for x in raw) if m is not None]
    mods.sort(key=lambda m: (m.updated_at or "", m.id), reverse=True)
    return mods


def upsert_module(module: TrustedModule) -> list[TrustedModule]:
    """新增或按 id 覆盖一个模块（搜到同 topic 即更新，不重复建）。"""
    mods = {m.id: m for m in load_modules()}
    prev = mods.get(module.id)
    now = _now()
    module.created_at = (prev.created_at if prev else "") or module.created_at or now
    module.updated_at = now
    mods[module.id] = module
    _write_section("modules", [m.to_dict() for m in mods.values()])
    return load_modules()


def delete_module(mid: str) -> list[TrustedModule]:
    """删模块；不存在则原样返回（幂等）。"""
    mods = {m.id: m for m in load_modules()}
    mods.pop(mid, None)
    _write_section("modules", [m.to_dict() for m in mods.values()])
    return load_modules()


def add_module_item(mid: str, entry: SourceEntry) -> list[TrustedModule]:
    """往指定模块加/覆盖一条条目（同标题覆盖）。"""
    mods = {m.id: m for m in load_modules()}
    target = mods.get(mid)
    if target is None:
        raise KeyError(f"模块不存在：{mid}")
    target.items = [e for e in target.items if e.title != entry.title]
    target.items.append(entry)
    target.origin = "manual"  # 手工动过就标 manual，避免被误当纯 AI 生成
    return upsert_module(target)


def remove_module_item(mid: str, title: str) -> list[TrustedModule]:
    """从模块删一条条目。"""
    mods = {m.id: m for m in load_modules()}
    target = mods.get(mid)
    if target is None:
        raise KeyError(f"模块不存在：{mid}")
    target.items = [e for e in target.items if e.title != title]
    return upsert_module(target)


# ---------- 可信源（平台）注册表 ----------


def load_user_platforms() -> list[Source]:
    """用户侧平台（AI 自动收录 / 设置页手工加），存 `settings.json` 的 `platforms`。"""
    raw = load_settings().get("platforms") or []
    return [s for s in (parse_source(x) for x in raw) if s is not None and s.id]


def load_platforms() -> list[Source]:
    """全部平台 = 内置（`config/sources.yml`，curated 真相源） + 用户侧；按 id 去重，**内置优先**。

    内置优先的理由：`github.com` 就是 GitHub，谁先定义好就用谁的——用户侧重复收录同一站时
    只会命中内置那条，不会长成第二个 GitHub。
    """
    merged: dict[str, Source] = {}
    for raw in load_sources().get("platforms") or []:
        src = parse_source(raw)
        if src is not None and src.id:
            merged.setdefault(src.id, src)
    for src in load_user_platforms():
        merged.setdefault(src.id, src)
    return list(merged.values())


def register_platforms(sources: list[Source]) -> list[Source]:
    """把平台**补进**注册表：id 已存在（内置或已收录）的跳过，不覆盖、不重复。

    返回全量平台清单。落盘点只在 `platforms` 一段，模块与历史不受影响。
    """
    known = {s.id for s in load_platforms()}
    user = {s.id: s for s in load_user_platforms()}
    added = False
    for src in sources:
        if not src.id:
            src.id = platform_id(src.name, src.home)
        if not src.id or src.id in known:
            continue
        known.add(src.id)
        user[src.id] = src
        added = True
    if added:
        _write_section("platforms", [s.to_dict() for s in user.values()])
    return load_platforms()


def remove_platform(pid: str) -> list[Source]:
    """删一个用户侧平台（内置平台删不掉——它在 `config/sources.yml` 里，删了也会回来）。

    条目引用它的地方会显示成「未登记来源」，不损坏数据；重新收录同域名即恢复。
    """
    user = {s.id: s for s in load_user_platforms()}
    user.pop(pid, None)
    _write_section("platforms", [s.to_dict() for s in user.values()])
    return load_platforms()


# ---------- 搜索历史 ----------


def load_history(limit: int = HISTORY_LIMIT) -> list[HistoryItem]:
    """读搜索历史（按时间倒序，最近搜的在最前）。"""
    raw = load_settings().get("history") or []
    items = [h for h in (_parse_history(x) for x in raw) if h is not None]
    items.sort(key=lambda h: h.at, reverse=True)
    return items[:limit]


def record_search(topic: str, matched: bool, source_count: int) -> list[HistoryItem]:
    """记一条搜索历史：同主题只保留一条（再搜一次 = 顶到最前并刷新结果），上限 `HISTORY_LIMIT`。"""
    key = module_id(topic)
    if not key:
        return load_history()
    others = [h for h in load_history(limit=HISTORY_LIMIT * 2) if module_id(h.topic) != key]
    head = HistoryItem(topic=topic.strip(), at=_now(), matched=matched, source_count=source_count)
    merged = [head, *others][:HISTORY_LIMIT]
    _write_section("history", [h.to_dict() for h in merged])
    return merged


def clear_history() -> list[HistoryItem]:
    """清空搜索历史。"""
    _write_section("history", [])
    return []


_ASCII_ONLY = re.compile(r"^[\x00-\x7f]+$")


def matches_keywords(keywords: list[str], fields: list[str]) -> bool:
    """关键词是否命中这些字段（topic / keywords / 源名）。

    **ASCII 词按整词匹配**——实测踩坑：搜 `transform` 会因 `"transform" in
    "Sentence Transformers"` 命中一个 RAG 模块、`ai` 会命中 `FAISS`，于是"找到可信源"其实
    是误命中，把不相关的源端给了用户。不做单复数容错（`transformer` vs `Transformers`
    也是两个意思）——宁可漏掉缓存回落 AI 判定，也不给错源。
    中文按子串匹配：中文没有词边界，子串才是有意义的包含（如「向量数据库」⊂「向量数据库与相似度检索」）。
    """
    raw = " ".join(fields)
    lowered = raw.lower()
    folded = fold(raw)
    for k in keywords:
        kw = fold(k)
        if not kw:
            continue
        if _ASCII_ONLY.match(kw):
            if re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", lowered):
                return True
        elif kw in folded:
            return True
    return False


def match_modules(keywords: list[str]) -> list[TrustedModule]:
    """按关键词命中模块：topic / keywords / 条目标题 / 平台名 任一命中即算。

    ⚠ 平台 **id（域名）不参与匹配**：`ai` 会整词命中 `faiss.ai`，把不相关的模块当缓存命中
    （实测踩坑同 `transform`/`FAISS`）。名字可以（GitHub / arXiv 是有意义的锚点），域名不行。
    """
    names = {s.id: s.name for s in load_platforms()}
    hits: list[TrustedModule] = []
    for m in load_modules():
        fields = [
            m.topic,
            *m.keywords,
            *(e.title for e in m.items),
            *(names.get(e.source, "") for e in m.items),
        ]
        if matches_keywords(keywords, fields):
            hits.append(m)
    return hits


def find_module(topic: str) -> TrustedModule | None:
    """按 topic 精确查模块（id 由 `module_id` 归一）。

    模块即缓存，**缓存键就是 topic**——只按关键词包含匹配的话，在线时 orient 出的是长短语
    （如「RAG评估指标与优化方法」），几乎碰不上已有模块，同一主题每次都重新烧 token 判定。
    """
    mid = module_id(topic)
    if not mid:
        return None
    return next((m for m in load_modules() if m.id == mid), None)


# ---------- 模型资源（`data/settings/llm.json`）----------
#
# 为什么要落盘而不是只读 `.env`：模型配置是**要天天调**的东西（换模型、加一家、调链序、改超时），
# 让用户改 `.env` 再重启不现实。分工：`.env` = 出厂/运维配置（也是本文件的**播种源**），
# 界面上存出来的 llm.json = 用户配置，**一旦存在即为唯一真源**（成熟工具皆如此：env 只做 bootstrap）。
# 该文件在 data/settings/ 下，已 gitignore；明文 Key 写这里与写 `.env` 同级风险，
# 故 provider 也支持 `apiKeyEnv`：**引用环境变量名，密钥不落盘**（默认家就是这么播的）。

LLM_CONFIG_PATH = SETTINGS_DIR / "llm.json"
LLM_CHAIN_MODES: tuple[str, ...] = ("fallback", "moa")

_PREFIX = "LLM_PROVIDER_"


@dataclass
class LlmProvider:
    """一家资源 = base_url + 凭据。凭据二选一：明文 `api_key`，或 `api_key_env` 引用的环境变量名。"""

    id: str
    base_url: str
    api_key: str = ""
    api_key_env: str = ""

    def resolve_key(self) -> str:
        """明文优先（允许界面覆盖 .env），否则取引用的环境变量。"""
        return self.api_key or os.environ.get(self.api_key_env, "").strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "baseUrl": self.base_url,
            "apiKey": self.api_key,
            "apiKeyEnv": self.api_key_env,
        }


@dataclass
class LlmChain:
    """一个档位的链路。`fallback` 逐个试到成功；`moa` 都跑一遍再融合（多模型共识）。"""

    mode: str = "fallback"
    entries: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"mode": self.mode, "entries": list(self.entries)}


@dataclass
class LlmConfig:
    providers: list[LlmProvider] = field(default_factory=list)
    chains: dict[str, LlmChain] = field(default_factory=dict)
    default_provider: str = ""
    max_attempts: int = 3
    timeout: float = 60.0
    source: str = "env"  # env（按 .env 播种）| file（界面存过）


def _os_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _seed_providers() -> list[LlmProvider]:
    """按 `.env` 播种 provider。缺 base_url 或缺 key 的不进池——没填即不启用，对运行零影响。

    默认家的 id 不写死厂商名（缺 `LLM_DEFAULT_PROVIDER` 时叫 `default`）：改一家只需改 `.env`。
    """
    out: list[LlmProvider] = []
    base = _os_env("LLM_BASE_URL")
    if base:
        out.append(
            LlmProvider(
                id=_os_env("LLM_DEFAULT_PROVIDER") or "default",
                base_url=base,
                api_key_env="LLM_API_KEY",
            )
        )
    seen = {p.id.lower() for p in out}
    for name, value in os.environ.items():
        if not (name.startswith(_PREFIX) and name.endswith("_BASE_URL")) or not value.strip():
            continue
        pid = name[len(_PREFIX) : -len("_BASE_URL")].strip().lower()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        out.append(
            LlmProvider(id=pid, base_url=value.strip(), api_key_env=f"{_PREFIX}{pid.upper()}_API_KEY")
        )
    return out


def _seed_chains() -> dict[str, LlmChain]:
    """按 `.env` 播种链路。模式写成前缀：`moa:gpt-plus,glm-flash` / 默认 fallback。"""
    out: dict[str, LlmChain] = {}
    for tier in ("main", "cheap"):
        raw = _os_env(f"LLM_CHAIN_{tier.upper()}")
        if not raw:
            continue
        mode = "fallback"
        head, sep, rest = raw.partition(":")
        if sep and head.strip().lower() in LLM_CHAIN_MODES:
            mode, raw = head.strip().lower(), rest
        entries = [e.strip() for e in raw.split(",") if e.strip()]
        if entries:
            out[tier] = LlmChain(mode=mode, entries=entries)
    return out


def _seed_from_env() -> LlmConfig:
    return LlmConfig(
        providers=_seed_providers(),
        chains=_seed_chains(),
        default_provider=_os_env("LLM_DEFAULT_PROVIDER") or "default",
        max_attempts=_int_env("LLM_MAX_ATTEMPTS", 3),
        timeout=_float_env("LLM_TIMEOUT", 60.0),
        source="env",
    )


def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(_os_env(name) or default))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return max(1.0, float(_os_env(name) or default))
    except ValueError:
        return default


def _parse_llm_config(raw: dict[str, Any]) -> LlmConfig:
    providers: list[LlmProvider] = []
    items = raw.get("providers")
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            pid = str(item.get("id", "")).strip()
            base_url = str(item.get("baseUrl", "")).strip()
            if pid and base_url:
                providers.append(
                    LlmProvider(
                        id=pid,
                        base_url=base_url,
                        api_key=str(item.get("apiKey", "")).strip(),
                        api_key_env=str(item.get("apiKeyEnv", "")).strip(),
                    )
                )
    chains: dict[str, LlmChain] = {}
    raw_chains = raw.get("chains")
    if isinstance(raw_chains, dict):
        for tier, item in raw_chains.items():
            if not isinstance(item, dict):
                continue
            mode = str(item.get("mode", "fallback")).strip().lower()
            entries_raw = item.get("entries")
            entries = (
                [str(e).strip() for e in entries_raw if str(e).strip()]
                if isinstance(entries_raw, list)
                else []
            )
            chains[str(tier)] = LlmChain(
                mode=mode if mode in LLM_CHAIN_MODES else "fallback", entries=entries
            )
    return LlmConfig(
        providers=providers,
        chains=chains,
        default_provider=str(raw.get("defaultProvider", "")).strip() or "default",
        max_attempts=max(1, int(raw.get("maxAttempts") or 3)),
        timeout=max(1.0, float(raw.get("timeout") or 60.0)),
        source="file",
    )


def load_llm_config() -> LlmConfig:
    """读模型资源配置：界面存过就以文件为准，否则按 `.env` 播种（文件损坏同样回落播种）。"""
    if not LLM_CONFIG_PATH.exists():
        return _seed_from_env()
    try:
        raw = json.loads(LLM_CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _seed_from_env()
    if not isinstance(raw, dict):
        return _seed_from_env()
    return _parse_llm_config(raw)


def _mask(value: str) -> str:
    return f"{value[:6]}…{value[-4:]}" if len(value) > 12 else "…"


def _key_hint(provider: LlmProvider) -> str:
    if provider.api_key:
        return f"明文（本机 llm.json）：{_mask(provider.api_key)}"
    if not provider.api_key_env:
        return "未填 Key"
    if os.environ.get(provider.api_key_env):
        return f"来自环境变量 ${provider.api_key_env}"
    return f"环境变量 ${provider.api_key_env} 未设置"


def llm_config_payload() -> dict[str, Any]:
    """给界面的配置视图：**明文 Key 不回传**，只给 `hasKey` 与脱敏提示。"""
    cfg = load_llm_config()
    return {
        "source": cfg.source,
        "path": str(LLM_CONFIG_PATH),
        "defaultProvider": cfg.default_provider,
        "maxAttempts": cfg.max_attempts,
        "timeout": cfg.timeout,
        "providers": [
            {
                "id": p.id,
                "baseUrl": p.base_url,
                "apiKey": "",
                "apiKeyEnv": p.api_key_env,
                "hasKey": bool(p.resolve_key()),
                "keyHint": _key_hint(p),
            }
            for p in cfg.providers
        ],
        "chains": {
            tier: {"mode": c.mode, "entries": list(c.entries)} for tier, c in cfg.chains.items()
        },
    }


def save_llm_config_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """界面存配置。`apiKey` 留空 = **不改**（界面只回显脱敏值，不回传明文），要换就重填、要清就删这家。"""
    parsed = _parse_llm_config(raw)
    prev = {p.id: p for p in load_llm_config().providers}
    for provider in parsed.providers:
        if provider.api_key or provider.api_key_env:
            continue
        old = prev.get(provider.id)
        if old is not None:
            provider.api_key, provider.api_key_env = old.api_key, old.api_key_env
    LLM_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = LLM_CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(
            {
                "defaultProvider": parsed.default_provider,
                "providers": [p.to_dict() for p in parsed.providers],
                "chains": {t: c.to_dict() for t, c in parsed.chains.items()},
                "maxAttempts": parsed.max_attempts,
                "timeout": parsed.timeout,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    tmp.replace(LLM_CONFIG_PATH)
    return llm_config_payload()
