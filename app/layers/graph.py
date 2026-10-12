"""L4 · 图谱层：多 topic 组合成全局串联图谱（价值层）。

挂载闭环：新知识向量化 → cosine 召回近邻（哪些相关）→ LLM 判边（什么关系）→ 置信度门 → 挂边。
关系 schema：递进（竖·深度，实体↔实体）/ 应用（锚点，机制卡↔实体，由 mechanism.attach_cards 生成）。
类比不再是边：两个实体共享同一张机制卡即涌现（见 app/layers/mechanism.py 的 analogies_of）。
cosine 只做召回，判边才是串联。产物落 `data/graph/edges.md`。

**降级（L2 级，记录在案）**：未配 embedding/LLM 时——
- 召回：`cosine（真向量）` → 降级为 `字面 bigram Jaccard`（stub 向量是哈希噪声，拿它召回无意义）；
- 判边：`LLM 判边` → 降级为「同域→递进 / 跨域→无关」启发式（跨域同构改由机制卡承载）；
- 阈值门 `min_score` 照常生效（宁缺勿滥）：离线时跨域噪声大多被挡下，只留真正的字面重合。
"""
from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from app.config import DATA, load_schema
from app.layers.topology import all_entities, entity_domains, normalize
from app.llm import chat_json, is_online, relation_schema_hint
from app.models import Edge, Namespace
from app.rag.embed import cosine_similarity, embed

__all__ = ["DEFAULT_MIN_SCORE", "EDGES_PATH", "attach", "judge", "load_edges", "recall", "write_edges"]

EDGES_PATH: Path = DATA / "graph" / "edges.md"

# 召回阈值：低于它不进判边（宁缺勿滥）。离线字面相似度天然偏低，故取小值。
DEFAULT_MIN_SCORE = 0.12

_ROW_RE = re.compile(r"^\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]*)\|\s*$", re.M)
_VALID_TYPES = ("递进", "应用")


def _bigrams(text: str) -> set[str]:
    s = normalize(text)
    if len(s) < 2:
        return {s} if s else set()
    return {s[i : i + 2] for i in range(len(s) - 1)}


def _lexical_similarity(a: str, b: str) -> float:
    """离线召回用：字符 bigram Jaccard（对中文实体名有意义，且确定性可测）。"""
    ga, gb = _bigrams(a), _bigrams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)



def load_edges(path: Path | None = None) -> list[Edge]:
    """读 edges.md 的表格行（跳过表头与分隔行）。"""
    p = path or EDGES_PATH
    if not p.exists():
        return []
    edges: list[Edge] = []
    for m in _ROW_RE.finditer(p.read_text(encoding="utf-8")):
        src, etype, dst, note = (g.strip() for g in m.groups())
        if etype not in _VALID_TYPES or src in {"源", "---"} or set(src) <= {"-"}:
            continue
        edges.append(Edge(src=src, dst=dst, type=etype, confidence="high", reason=note))  # type: ignore[arg-type]
    return edges


def recall(namespace: Namespace, top_k: int = 10, min_score: float = DEFAULT_MIN_SCORE) -> list[tuple[str, str, float]]:
    """召回：本 namespace 实体 vs 已有全局实体。

    返回 (本方实体键, 对方实体键, 相似度) 降序——配对「最像的那一对」，
    而不是拿任意本方实体去判边（否则判出来的边是噪声）。

    相似度来源：配了 embedding → 真向量 cosine；否则降级为字面 bigram Jaccard。
    低于 min_score 的候选直接丢弃（宁缺勿滥）。
    """
    if not namespace.entities:
        return []
    known = all_entities()
    own = [normalize(e.name) for e in namespace.entities]
    own_set = set(own)
    targets = [k for k in known if k not in own_set]
    if not targets:
        return []

    use_real_embedding = bool(os.environ.get("EMBEDDING_BASE_URL") and os.environ.get("EMBEDDING_API_KEY"))
    best: dict[str, tuple[str, float]] = {}
    if use_real_embedding:
        query = embed(own, backend="api")
        corpus = embed(targets, backend="api")
        for src, qv in zip(own, query, strict=True):
            for dst, cv in zip(targets, corpus, strict=True):
                score = cosine_similarity(qv, cv)
                cur = best.get(dst)
                if cur is None or score > cur[1]:
                    best[dst] = (src, score)
    else:
        for src in own:
            for dst in targets:
                score = _lexical_similarity(src, dst)
                cur = best.get(dst)
                if cur is None or score > cur[1]:
                    best[dst] = (src, score)

    ranked = [(src, dst, sc) for dst, (src, sc) in best.items() if sc >= min_score]
    ranked.sort(key=lambda t: (-t[2], t[1]))
    return ranked[:top_k]


def judge(src: str, dst: str) -> Edge | None:
    """判实体↔实体的递进边；无关/跨域/未建卡返回 None。应用边与类比见 mechanism 层。"""
    if is_online():
        data = chat_json(
            "你是知识图谱的关系判边器。" + relation_schema_hint(),
            f"节点 A（新学）：{src}\n节点 B（候选近邻）：{dst}\n"
            '只输出 JSON：{"edge":"递进|无关","direction":"A→B|B→A|null","confidence":"high|low","reason":""}',
        )
        etype = str(data.get("edge", "")).strip()
        if etype == "递进":
            direction = str(data.get("direction", "A→B")).strip()
            a, b = (src, dst) if "B→A" not in direction else (dst, src)
            return Edge(
                src=a,
                dst=b,
                type="递进",
                confidence=str(data.get("confidence", "low")).strip() or "low",
                reason=str(data.get("reason", "")).strip(),
            )
        if etype == "无关":
            return None
        # etype 为空（LLM 失败/被拦）→ 落到离线启发式兜底
    # 离线启发式：同域 → 递进；跨域/未建卡 → 无边。
    # 必须先 normalize 再查 —— entity_domains() 键是归一化的（去空白+小写），直接拿展示名查会全落空（实测 bug）。
    domains = entity_domains()
    src_key, dst_key = normalize(src), normalize(dst)
    ds, dd = domains.get(src_key, ""), domains.get(dst_key, "")
    if ds and dd and ds == dd:
        return Edge(src=src_key, dst=dst_key, type="递进", confidence="high", reason=f"同域（{ds}），按 schema 归递进")
    return None


def attach(
    namespace: Namespace,
    *,
    top_k: int = 5,
    min_score: float = DEFAULT_MIN_SCORE,
    dry_run: bool = False,
) -> list[Edge]:
    """新 namespace → 挂进全局图谱，返回新增的边（默认写盘）。

    顺序：① 抽机制卡并挂应用边（卡↔实体）→ ② 召回+判边挂递进边 → ③ 内部关系升格 → 去重写盘。
    """
    from app.layers import mechanism  # 延迟导入：避免 layers 之间循环

    known = all_entities()
    own = {normalize(e.name) for e in namespace.entities}
    new_edges: list[Edge] = []

    # 1) 机制卡：抽取 → 入库 → 挂应用边（卡 → 实体）
    cards = mechanism.extract_cards(namespace)
    if cards:
        mechanism.upsert_cards(cards)
        new_edges.extend(mechanism.attach_cards(cards))

    # 2) cosine 召回最像的一对 → 判递进边
    for src_key, dst_key, _score in recall(namespace, top_k=top_k, min_score=min_score):
        edge = judge(src_key, dst_key)
        if edge is not None and edge.confidence == "high":
            new_edges.append(edge)

    # 3) namespace 内部关系（来自 L3）直接升格为图谱边
    for rel in namespace.relations:
        if rel.src in known or rel.src in own or rel.dst in known or rel.dst in own:
            new_edges.append(
                Edge(src=rel.src, dst=rel.dst, type=rel.type, confidence="high", reason="namespace 内部关系")
            )

    # 4) 去重（同 src/dst/type）
    dedup: list[Edge] = []
    seen: set[tuple[str, str, str]] = set()
    for e in new_edges:
        key = (e.src, e.dst, e.type)
        if key not in seen:
            seen.add(key)
            dedup.append(e)

    if not dry_run and dedup:
        write_edges(dedup)
    return dedup


def write_edges(edges: list[Edge], path: Path | None = None) -> Path:
    """把新边追加到 edges.md 的两个分区（递进 / 应用）。

    去重键用归一化后的端点（= 图上的节点身份）——大小写不同的同一对端点算同一条边。
    实测：手写边 `JMM内存模型` 与生成边 `jmm内存模型` 共存，会让图上多出重复线。
    """
    p = path or EDGES_PATH
    existing = load_edges(p)
    merged: dict[tuple[str, str, str], Edge] = {}
    for e in [*existing, *edges]:
        merged.setdefault((normalize(e.src), normalize(e.dst), e.type), e)
    all_edges = list(merged.values())

    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 全局串联图谱 · 边（稀疏，只留可迁移边）",
        "",
        "> 由 `app/layers/graph.py` 维护；手工编辑亦可。两类边，带方向。",
        "",
        "## 递进边（竖线·深度，领域内）",
        "| 源 | 边 | 目标 | 说明 |",
        "|---|---|---|---|",
    ]
    for e in all_edges:
        if e.type == "递进":
            lines.append(f"| {e.src} | 递进 | {e.dst} | {e.reason} |")
    lines += ["", "## 应用边（横线·锚点，机制卡 → 实体）", "| 源 | 边 | 目标 | 说明 |", "|---|---|---|---|"]
    for e in all_edges:
        if e.type == "应用":
            lines.append(f"| {e.src} | 应用 | {e.dst} | {e.reason} |")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def schema_types() -> tuple[str, ...]:
    """schema 里允许的关系类型（供 CLI 展示/校验）。"""
    schema = load_schema()
    return tuple((schema.get("relations") or {}).keys()) or _VALID_TYPES
