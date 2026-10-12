"""nanoRAG · L4 融合（RRF，Reciprocal Rank Fusion）。

契约（先读 test_fuse.py 再实现）：
reciprocal_rank_fusion(ranked_lists, k=60)：
- 输入：多条路的排名，每条路是「已按相关度从高到低排好」的 id 列表。
- 每个 id 的融合分 = sum(1 / (k + rank))，rank 从 1 起，跨所有出现它的路累加。
- 输出：按融合分从高到低排序的 id 列表。
- 分数相同时，按「首次出现顺序」稳定排列（扫描 ranked_lists 按序、列表内按序）。

关键点：RRF 只用「排名」，不用「分数」——所以不同路分数量纲不同也没关系。这是它能稳的原因。
"""

__all__ = ["reciprocal_rank_fusion"]


def reciprocal_rank_fusion(ranked_lists: list[list[str]], k: int = 60) -> list[str]:
    """多条排名 → 一条融合排名。"""
    scores: dict[str, float] = {}
    first_seen: dict[str, int] = {}
    for ranked in ranked_lists:
        for rank, doc in enumerate(ranked, start=1):
            scores[doc] = scores.get(doc, 0.0) + 1.0 / (k + rank)
            if doc not in first_seen:
                first_seen[doc] = len(first_seen)
    return sorted(scores, key=lambda d: (-scores[d], first_seen[d]))
