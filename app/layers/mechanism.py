"""L4 · 机制卡层：把可迁移的「解法动作」抽象成机制卡（一等公民）。

卡/实例两层：机制卡决定网的高度（金线），实体构成网的密度（网体）；
类比 = 两个实体共享同一张卡的涌现（非边，见 analogies_of）。产物落 data/mechanism/cards.md。
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from app.config import DATA, ROOT
from app.layers.topology import normalize
from app.llm import chat_json, is_online
from app.models import Edge, MechanismCard, Namespace

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "CARDS_PATH",
    "analogies_of",
    "attach_cards",
    "extract_cards",
    "load_cards",
    "upsert_cards",
]

CARDS_PATH = DATA / "mechanism" / "cards.md"
_EXTRACT_PROMPT = ROOT / "prompts" / "mechanism_extraction.md"

_CARD_RE = re.compile(r"^##\s+(.+?)\s*$")


def _parse_card_block(name: str, text: str) -> MechanismCard:
    """解析一张卡的 `key: value` 字段块；cases 用顿号/逗号分隔。"""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fields[k.strip()] = v.strip()
    cases = [c.strip() for c in re.split(r"[、，,]", fields.get("cases", "")) if c.strip()]
    return MechanismCard(
        name=name.strip(),
        problem=fields.get("problem", ""),
        mechanism=fields.get("mechanism", ""),
        tradeoff=fields.get("tradeoff", ""),
        boundary=fields.get("boundary", ""),
        cases=cases,
    )


def load_cards(path: Path | None = None) -> list[MechanismCard]:
    """读 cards.md → 机制卡清单（离线确定性，不调 LLM）。"""
    p = path or CARDS_PATH
    if not p.exists():
        return []
    cards: list[MechanismCard] = []
    current: str | None = None
    buf: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        m = _CARD_RE.match(line)
        if m:
            if current is not None:
                cards.append(_parse_card_block(current, "\n".join(buf)))
            current = m.group(1).strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        cards.append(_parse_card_block(current, "\n".join(buf)))
    return cards


def _write_cards(cards: list[MechanismCard], path: Path) -> Path:
    """把机制卡清单写回 cards.md（整文件重写，保持单一真相源）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 机制卡库（L4 一等公民）",
        "",
        "> 每卡以 `## <卡名>` 起始，字段 `key: value`；cases 用顿号/逗号分隔。",
        "> 由 `app/layers/mechanism.py` 维护；手工编辑亦可。卡名用动词锚定（如「攒批写」）。",
        "",
    ]
    for c in cards:
        lines.append(f"## {c.name}")
        lines.append(f"problem: {c.problem}")
        lines.append(f"mechanism: {c.mechanism}")
        lines.append(f"tradeoff: {c.tradeoff}")
        lines.append(f"boundary: {c.boundary}")
        lines.append(f"cases: {'、'.join(c.cases)}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def upsert_cards(cards: list[MechanismCard], path: Path | None = None) -> list[MechanismCard]:
    """合并新卡进库（同名归一后合并 cases），落盘后返回全量清单。"""
    p = path or CARDS_PATH
    merged: dict[str, MechanismCard] = {}
    for c in load_cards(p) + cards:
        key = normalize(c.name)
        prev = merged.get(key)
        if prev is None:
            merged[key] = MechanismCard(name=c.name, problem=c.problem, mechanism=c.mechanism,
                                        tradeoff=c.tradeoff, boundary=c.boundary, cases=list(c.cases))
            continue
        # 同名卡：cases 去重合并，字段以「有值的为准」（新卡可补旧卡空白字段）
        seen = set(prev.cases)
        prev.cases = prev.cases + [x for x in c.cases if x not in seen]
        if c.problem:
            prev.problem = c.problem
        if c.mechanism:
            prev.mechanism = c.mechanism
        if c.tradeoff:
            prev.tradeoff = c.tradeoff
        if c.boundary:
            prev.boundary = c.boundary
    result = list(merged.values())
    _write_cards(result, p)
    return result


def attach_cards(cards: list[MechanismCard]) -> list[Edge]:
    """机制卡 → 实体的应用边（确定性：卡 cases 里出现谁就挂谁）。"""
    edges: list[Edge] = []
    for card in cards:
        for case in card.cases:
            if case:
                edges.append(
                    Edge(src=card.name, dst=case, type="应用", confidence="high",
                         reason=f"机制卡「{card.name}」作用于 {case}")
                )
    return edges


def analogies_of(entity: str, cards: list[MechanismCard] | None = None) -> list[dict[str, Any]]:
    """类比涌现：找出与 entity 共享同一张机制卡的其他实体（纯查询，不落盘）。"""
    all_cards = load_cards() if cards is None else cards
    key = normalize(entity)
    out: list[dict[str, Any]] = []
    for card in all_cards:
        cases = [normalize(c) for c in card.cases]
        if key in cases:
            siblings = [c for c in card.cases if normalize(c) != key]
            if siblings:
                out.append({"card": card.name, "siblings": siblings})
    return out


@lru_cache(maxsize=1)
def _extract_system_prompt() -> str:
    """prompt 是资产，单一真相源在文件里。"""
    return _EXTRACT_PROMPT.read_text(encoding="utf-8")


def extract_cards(namespace: Namespace) -> list[MechanismCard]:
    """从 namespace 的实体提炼机制卡。有 LLM 时抽；离线返回 []（宁缺勿滥）。"""
    if not is_online():
        return []
    entity_text = "\n".join(f"- {e.name}：{e.one_line}" for e in namespace.entities if e.one_line)
    if not entity_text:
        return []
    data = chat_json(
        _extract_system_prompt(),
        f"主题：{namespace.topic}\n实体清单：\n{entity_text}\n"
        '只输出 JSON：{"cards":[{"name":"","problem":"","mechanism":"","tradeoff":"","boundary":"","cases":["..."]}]}',
    )
    out: list[MechanismCard] = []
    for raw in data.get("cards") or []:
        if not isinstance(raw, dict) or not str(raw.get("name", "")).strip():
            continue
        cases = [str(c).strip() for c in raw.get("cases") or [] if str(c).strip()]
        out.append(
            MechanismCard(
                name=str(raw.get("name", "")).strip(),
                problem=str(raw.get("problem", "")).strip(),
                mechanism=str(raw.get("mechanism", "")).strip(),
                tradeoff=str(raw.get("tradeoff", "")).strip(),
                boundary=str(raw.get("boundary", "")).strip(),
                cases=cases,
            )
        )
    return out
