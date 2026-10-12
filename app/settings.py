"""用户设置（运行时状态，不入 git）。

存放 `data/settings/settings.json`。与 `config/*.yml` 的分工：
- `config/sources.yml` 的 `domains` = 随仓库走的**内置模块**（curated 真相源）；
- 这里的 `modules` = 用户侧的**搜索模块**，与内置 domains **同构**。

## 什么是「搜索模块」
一个模块 = 一个 topic 的可信源集合（不是一条条散装源）。例：

    {id: "java多线程·内存可见性", topic: "Java 多线程 · 内存可见性",
     keywords: [...], origin: "auto", sources: [...]}

`origin` 区分来路：
- `auto`   —— 搜主题时 AI 判定后**自动收录**（下次同 topic 直接命中，不再烧 token）；
- `manual` —— 在设置页手工建/改。

## 为什么以模块为单位
「可信源」天生是**按主题组织**的：同一份「JLS §17」对别的主题没意义。
扁平列表既无法按主题命中，也无法区分「这个源是为哪个主题找的」。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.config import DATA
from app.models import Source

__all__ = [
    "SETTINGS_PATH",
    "TrustedModule",
    "add_module_source",
    "delete_module",
    "load_modules",
    "load_settings",
    "match_modules",
    "remove_module_source",
    "save_settings",
    "upsert_module",
]

SETTINGS_DIR = DATA / "settings"
SETTINGS_PATH = SETTINGS_DIR / "settings.json"
TZ = ZoneInfo("Asia/Shanghai")

VALID_TYPES: tuple[str, ...] = ("规范", "源码", "书籍", "论文", "博客", "社区")
ORIGINS: tuple[str, ...] = ("auto", "manual")


@dataclass
class TrustedModule:
    """一个搜索模块：某 topic 的可信源集合。"""

    id: str
    topic: str
    origin: str = "manual"  # auto | manual
    keywords: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "origin": self.origin,
            "keywords": list(self.keywords),
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "sources": [
                {"name": s.name, "type": s.type, "why": s.why, "locator": s.locator} for s in self.sources
            ],
        }


def module_id(topic: str) -> str:
    """由 topic 派生稳定 id：同一主题只有一个模块（重复搜索即更新，不新增）。"""
    return re.sub(r"\s+", "", (topic or "").strip()).lower()


def _now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def _norm(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _parse_source(raw: object) -> Source | None:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name", "")).strip()
    if not name:
        return None
    stype = str(raw.get("type", "博客")).strip()
    if stype not in VALID_TYPES:
        stype = "博客"
    return Source(
        name=name,
        type=stype,  # type: ignore[arg-type]
        why=str(raw.get("why", "")).strip(),
        locator=str(raw.get("locator", "")).strip(),
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
    raw_sources = raw.get("sources") or []
    sources = [s for s in (_parse_source(x) for x in raw_sources) if s is not None]
    keywords = [str(k).strip() for k in (raw.get("keywords") or []) if str(k).strip()]
    mid = str(raw.get("id", "")).strip() or module_id(topic)
    return TrustedModule(
        id=mid,
        topic=topic,
        origin=origin,
        keywords=keywords,
        sources=sources,
        created_at=str(raw.get("createdAt", "")),
        updated_at=str(raw.get("updatedAt", "")),
    )


def _migrate(raw: dict[str, Any]) -> dict[str, Any]:
    """旧格式（扁平 trusted_sources）→ 新格式（modules）。

    迁移成**一个手工模块**，而不是丢掉——但只在确实没有 modules 字段时做，
    且不写盘（等下一次写操作自然落成新格式）。
    """
    if "modules" in raw:
        return raw
    legacy = raw.get("trusted_sources") or []
    sources = [s for s in (_parse_source(x) for x in legacy) if s is not None]
    if not sources:
        return {"modules": []}
    return {
        "modules": [
            TrustedModule(
                id="migrated",
                topic="手工收录（旧格式迁移）",
                origin="manual",
                sources=sources,
                created_at=_now(),
                updated_at=_now(),
            ).to_dict()
        ]
    }


def load_settings() -> dict[str, Any]:
    """读设置；文件不存在/损坏时返回空结构（不让界面因缺文件而崩）。"""
    if not SETTINGS_PATH.exists():
        return {"modules": []}
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"modules": []}
    if not isinstance(raw, dict):
        return {"modules": []}
    return _migrate(raw)


def save_settings(data: dict[str, Any]) -> str:
    """原子写：先写临时文件再替换，避免中断留下半个 JSON。"""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(SETTINGS_PATH)
    return str(SETTINGS_PATH)


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
    save_settings({"modules": [m.to_dict() for m in mods.values()]})
    return load_modules()


def delete_module(mid: str) -> list[TrustedModule]:
    """删模块；不存在则原样返回。"""
    mods = {m.id: m for m in load_modules()}
    mods.pop(mid, None)
    save_settings({"modules": [m.to_dict() for m in mods.values()]})
    return load_modules()


def add_module_source(mid: str, source: Source) -> list[TrustedModule]:
    """往指定模块加/覆盖一条源（同名覆盖）。"""
    mods = {m.id: m for m in load_modules()}
    target = mods.get(mid)
    if target is None:
        raise KeyError(f"模块不存在：{mid}")
    target.sources = [s for s in target.sources if s.name != source.name]
    target.sources.append(source)
    target.origin = "manual"  # 手工动过就标 manual，避免被误当纯 AI 生成
    return upsert_module(target)


def remove_module_source(mid: str, name: str) -> list[TrustedModule]:
    """从模块删一条源。"""
    mods = {m.id: m for m in load_modules()}
    target = mods.get(mid)
    if target is None:
        raise KeyError(f"模块不存在：{mid}")
    target.sources = [s for s in target.sources if s.name != name]
    return upsert_module(target)


def _fold(value: str) -> str:
    """匹配用归一：小写 + 去空白（与 retrieve 同口径，大小写不敏感）。"""
    return re.sub(r"\s+", "", (value or "").lower())


def match_modules(keywords: list[str]) -> list[TrustedModule]:
    """按关键词命中模块：topic / keywords / 源名 任一处包含关键词即命中（大小写不敏感）。"""
    hits: list[TrustedModule] = []
    for m in load_modules():
        haystack = _fold(" ".join([m.topic, *m.keywords, *(s.name for s in m.sources)]))
        if any(k and _fold(k) in haystack for k in keywords):
            hits.append(m)
    return hits
