"""L3 · 拓扑层：可信源 → 单 namespace 拓扑（实体 + 关系 + 双链卡）。

步骤：抽实体 → 抽关系 → 实体对齐（同名/别名合并）→ 建双链卡。
产物落 `data/wiki/`（markdown 双链，git 为真相源），供 Obsidian 阅读。

**实体键 = 文件名 stem**（Obsidian `[[链接]]` 按文件名解析），标题仅作展示——
这条不做对，关系会全断（实测：标题带空格「JMM 内存模型」vs 链接 `JMM内存模型`）。

离线策略：解析 `data/wiki/notes/` 现有卡片（确定性、可测）；有 LLM 时从可信源正文抽取。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.config import DATA
from app.llm import chat_json, is_online
from app.models import Entity, Namespace, Relation, Source

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "NOTES_DIR",
    "WIKI_DIR",
    "all_entities",
    "build_namespace",
    "entity_domains",
    "load_namespace",
    "normalize",
    "topic_matches",
    "write_entity_cards",
]

WIKI_DIR = DATA / "wiki"
NOTES_DIR = WIKI_DIR / "notes"

_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)
_ONELINE_RE = re.compile(r"^##\s*一句话\s*\n+(.+?)\s*$", re.M)
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
_LINK_RE = re.compile(r"\[\[([^\]|#]+)")
_REL_SECTION_RE = re.compile(r"^##\s*(?:关系|关联|关键子节点)\s*\n(.*?)(?=^##\s|\Z)", re.M | re.S)

_DEFAULT_TYPE = "概念"


@dataclass
class _Card:
    key: str          # 文件名 stem（= Obsidian 链接目标 = 实体键）
    title: str        # 展示名
    domain: str
    etype: str
    one_line: str


def normalize(name: str) -> str:
    """对齐键：去空白 + 小写。`JMM 内存模型` / `jmm内存模型` 视为同一实体。"""
    return re.sub(r"\s+", "", (name or "").lower())


def _frontmatter(text: str) -> dict[str, str]:
    m = _FM_RE.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


def _parse_card(path: Path) -> _Card:
    text = path.read_text(encoding="utf-8")
    tm = _TITLE_RE.search(text)
    fm = _frontmatter(text)
    raw_type = fm.get("类型", "")
    etype = raw_type.split("·")[-1].strip() if raw_type else _DEFAULT_TYPE
    om = _ONELINE_RE.search(text)
    return _Card(
        key=path.stem,
        title=tm.group(1).strip() if tm else path.stem,
        domain=fm.get("领域", ""),
        etype=etype or _DEFAULT_TYPE,
        one_line=om.group(1).strip() if om else "",
    )


def _all_cards() -> list[_Card]:
    """只取 notes/ 下的实体卡（MOC / README 不是实体）。"""
    if not NOTES_DIR.exists():
        return []
    return [_parse_card(p) for p in sorted(NOTES_DIR.glob("*.md"))]


def _by_key(cards: list[_Card]) -> dict[str, _Card]:
    """对齐：同名（归一后）只留一张。"""
    out: dict[str, _Card] = {}
    for c in cards:
        out.setdefault(normalize(c.key), c)
    return out


def all_entities() -> dict[str, Entity]:
    """全部实体（跨 namespace）。键 = 归一化实体名。"""
    return {k: Entity(name=c.title, type=c.etype, one_line=c.one_line) for k, c in _by_key(_all_cards()).items()}


def entity_domains() -> dict[str, str]:
    """实体（归一化键）→ 所属领域；判边时区分「同域 / 跨域」。"""
    return {k: c.domain for k, c in _by_key(_all_cards()).items() if c.domain}


def _relations_of(card: _Card) -> list[Relation]:
    """从关系段抽边。三种历史写法都认（关系 / 关联 / 关键子节点）——按人的意图，不按标题字面。

    方向：`←` 或「上游」= 对方是前置（对方 → owner）；`→`、「下游」或裸链 = owner → 对方。
    类型：wiki 内的关系都是层级（is-a/contains/前置），统一归「递进」。
    """
    path = NOTES_DIR / f"{card.key}.md"
    if not path.exists():
        return []
    m = _REL_SECTION_RE.search(path.read_text(encoding="utf-8"))
    if not m:
        return []
    owner = normalize(card.key)
    rels: list[Relation] = []
    for line in m.group(1).splitlines():
        incoming = ("←" in line) or ("上游" in line)
        for link in _LINK_RE.finditer(line):
            target = normalize(link.group(1))
            if not target or target == owner:
                continue
            src, dst = (target, owner) if incoming else (owner, target)
            rels.append(Relation(src=src, dst=dst, type="递进"))
    return rels


def _topic_segments(topic: str) -> list[str]:
    """主题切段：`Java 多线程 · 内存可见性` → ['Java','多线程','内存可见性']（另含整串）。"""
    segs = [s for s in re.split(r"[·、,，/|;；\s]+", topic or "") if s]
    whole = normalize(topic)
    return [whole, *segs] if whole else segs


def topic_matches(card_key: str, card_domain: str, topic: str) -> bool:
    """宽松匹配：整串或任一段落在「实体键 / 领域」里（双向包含）。"""
    key, dom = normalize(card_key), normalize(card_domain)
    for seg in _topic_segments(topic):
        n = normalize(seg)
        if len(n) < 2:
            continue
        if n in key or key in n or (dom and (n in dom or dom in n)):
            return True
    return False


def load_namespace(topic: str = "") -> Namespace:
    """读现有 wiki（notes/）→ namespace；topic 命中领域或实体名时收窄。只读、不调 LLM。"""
    cards = _all_cards()
    if topic:
        matched = [c for c in cards if topic_matches(c.key, c.domain, topic)]
        if matched:
            cards = matched
    ns = Namespace(topic=topic or "全部")
    seen: set[str] = set()
    for c in cards:
        k = normalize(c.key)
        if k in seen:
            continue
        seen.add(k)
        ns.entities.append(Entity(name=c.title, type=c.etype, one_line=c.one_line))
        for rel in _relations_of(c):
            if rel not in ns.relations:
                ns.relations.append(rel)
    return ns


def build_namespace(topic: str, sources: list[Source]) -> Namespace:
    """可信源 → 单 namespace 拓扑。有 LLM 时抽取，否则解析现有 wiki 并挂上 sources。"""
    if is_online() and sources:
        src_text = "\n".join(f"- {s.name}（{s.type}）：{s.home}" for s in sources)
        data = chat_json(
            "你是知识拓扑梳理器。从可信源抽取实体与关系。",
            f"主题：{topic}\n可信源：\n{src_text}\n"
            '只输出 JSON：{"entities":[{"name":"","type":"概念|机制|产品|规范|人物","one_line":""}],'
            '"relations":[{"src":"","dst":"","type":"递进"}]}',
        )
        entities = [
            Entity(
                name=str(e.get("name", "")).strip(),
                type=str(e.get("type", _DEFAULT_TYPE)).strip() or _DEFAULT_TYPE,
                one_line=str(e.get("one_line", "")).strip(),
            )
            for e in data.get("entities") or []
            if isinstance(e, dict) and str(e.get("name", "")).strip()
        ]
        if entities:
            relations = [
                Relation(
                    src=str(r.get("src", "")).strip(),
                    dst=str(r.get("dst", "")).strip(),
                    # 取值来自 LLM JSON（边界），schema 由 prompts/relation_typing.md 约束
                    type=str(r.get("type", "递进")).strip(),  # type: ignore[arg-type]
                )
                for r in data.get("relations") or []
                if isinstance(r, dict) and str(r.get("src", "")).strip() and str(r.get("dst", "")).strip()
            ]
            return Namespace(topic=topic, sources=list(sources), entities=entities, relations=relations)
        # 在线但模型没抽出实体：宁空勿全——退回 load_namespace 会把全量旧实体当成「新结果」
        return Namespace(topic=topic, sources=list(sources))
    ns = load_namespace(topic)
    ns.sources = list(sources)
    return ns


def _stem(name: str) -> str:
    """文件名 stem = 实体名去空白（Obsidian 按文件名解析 `[[链接]]`，带空格会断链）。"""
    return re.sub(r"\s+", "", name or "")


def _link_name(name: str, by_key: dict[str, Entity]) -> str:
    """关系端点 → `[[链接]]` 目标：优先用实体真名（保留大小写，匹配已建卡的文件名）。"""
    ent = by_key.get(normalize(name))
    return _stem(ent.name if ent else name)


def write_entity_cards(
    namespace: Namespace,
    entities: list[Entity] | None = None,
    *,
    notes_dir: Path | None = None,
) -> list[str]:
    """把新实体写成双链卡 `data/wiki/notes/<stem>.md`（git 真相源）。

    - 已存在的卡**跳过**（不覆盖人工已写内容）；
    - `## 关系` 只写 namespace 内部关系（L3）；跨实体判出的边进 edges.md，不进卡；
    - 返回实际写入的文件 stem 清单。
    """
    out_dir = notes_dir or NOTES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    target = entities if entities is not None else namespace.entities
    by_key = {normalize(e.name): e for e in namespace.entities}
    domain = _stem(namespace.topic)
    written: list[str] = []
    for e in target:
        stem = _stem(e.name)
        if not stem:
            continue
        path = out_dir / f"{stem}.md"
        if path.exists():
            continue
        my = normalize(e.name)
        rels: list[str] = []
        for r in namespace.relations:
            if normalize(r.src) == my and normalize(r.dst) != my:
                rels.append(f"- → [[{_link_name(r.dst, by_key)}]]")
            elif normalize(r.dst) == my and normalize(r.src) != my:
                rels.append(f"- ← [[{_link_name(r.src, by_key)}]]")
        lines = [
            "---",
            f"领域: {domain}",
            f"类型: 实体·{e.type}",
            "---",
            "",
            f"# {e.name}",
            "",
            "## 一句话",
            e.one_line or "（待补）",
            "",
            "## 关系",
            *list(dict.fromkeys(rels)),
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append(stem)
    return written
