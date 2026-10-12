"""L5 · 画像层：抽象认知习惯（最后做）。

沉淀学习偏好 / 思维模式，反哺前面各层（如判边时带入个人偏好）。
低信噪比、长期工程；OpenViking 侧已有八维设计签名，此处是增量。

本版为**基础版**：从结构化事件流聚合出确定性统计（主题分布 / 关系类型偏好 / 活跃度）。
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from app.models import Profile

__all__ = ["distill", "load_events", "record_event"]

EVENTS_KEY = "events"


def distill(events: list[dict[str, Any]]) -> Profile:
    """学习行为 → 认知习惯画像（确定性聚合，不调 LLM）。"""
    topics: Counter[str] = Counter()
    relation_pref: Counter[str] = Counter()
    actions: Counter[str] = Counter()
    for ev in events:
        if not isinstance(ev, dict):
            continue
        topic = str(ev.get("topic", "")).strip()
        if topic:
            topics[topic] += 1
        rel = str(ev.get("relation_type", "")).strip()
        if rel:
            relation_pref[rel] += 1
        action = str(ev.get("action", "")).strip()
        if action:
            actions[action] += 1

    total = sum(topics.values()) or 1
    preferences: dict[str, Any] = {
        "events": len(events),
        "top_topics": topics.most_common(5),
        "topic_focus": round(max(topics.values()) / total, 3) if topics else 0.0,
        "relation_preference": dict(relation_pref),
        "actions": dict(actions),
    }
    if relation_pref:
        preferences["preferred_relation"] = relation_pref.most_common(1)[0][0]
    return Profile(preferences=preferences)


def load_events(path: str | None = None) -> list[dict[str, Any]]:
    """读事件流 JSONL（默认 data/profile/events.jsonl）。"""
    import json
    from pathlib import Path

    from app.config import DATA

    p = Path(path) if path else DATA / "profile" / "events.jsonl"
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def record_event(event: dict[str, Any], path: str | None = None) -> str:
    """追加一条事件到 JSONL（供 CLI 写入）。"""
    import json
    from pathlib import Path

    from app.config import DATA

    p = Path(path) if path else DATA / "profile" / "events.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return str(p)
