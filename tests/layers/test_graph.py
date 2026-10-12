"""L4 层验收：召回阈值 / 判边启发式 / 边读写（离线确定性路径）。"""
from app.layers.graph import (
    DEFAULT_MIN_SCORE,
    _lexical_similarity,
    attach,
    judge,
    load_edges,
    recall,
    write_edges,
)
from app.layers.topology import load_namespace
from app.models import Edge, Namespace


def test_lexical_similarity_is_bounded_and_deterministic():
    assert _lexical_similarity("", "x") == 0.0
    assert _lexical_similarity("abc", "abc") == 1.0
    mid = _lexical_similarity("JMM内存模型", "JMM内存布局")
    assert 0.0 < mid < 1.0
    assert mid == _lexical_similarity("JMM内存模型", "JMM内存布局")


def test_recall_respects_min_score():
    ns = load_namespace("Java 多线程 · 内存可见性")
    strict = recall(ns, top_k=20, min_score=0.99)
    loose = recall(ns, top_k=20, min_score=0.0)
    assert len(strict) <= len(loose)
    for _src, _dst, score in loose:
        assert score >= 0.0


def test_recall_never_returns_own_entities():
    ns = load_namespace("Java 多线程 · 内存可见性")
    own = {e.name for e in ns.entities}
    from app.layers.topology import all_entities

    known = all_entities()
    for _src, dst, _score in recall(ns, top_k=20, min_score=0.0):
        # dst 是归一化实体键（= 文件名 stem），必须能在全局实体表里解析到
        assert dst in known
        assert known[dst].name not in own


def test_judge_cross_domain_is_unrelated():
    assert judge("volatile", "Embedding是什么") is None


def test_judge_same_domain_is_prerequisite():
    edge = judge("volatile", "JMM内存模型")
    assert edge.type == "递进"


def test_edges_roundtrip(tmp_path):
    path = tmp_path / "edges.md"
    given = [
        Edge(src="A", dst="B", type="递进", reason="r1"),
        Edge(src="C", dst="D", type="应用", reason="r2"),
    ]
    write_edges(given, path)
    loaded = load_edges(path)
    assert len(loaded) == 2
    kinds = {(e.src, e.type, e.dst) for e in loaded}
    assert ("A", "递进", "B") in kinds
    assert ("C", "应用", "D") in kinds
    # 幂等：重复写不产生重复行
    write_edges(given, path)
    assert len(load_edges(path)) == 2


def test_attach_dry_run_does_not_write():
    ns = load_namespace("Java 多线程 · 内存可见性")
    edges = attach(ns, dry_run=True)
    assert edges, "dry-run 应算出边"
    assert all(e.type in {"递进", "应用"} for e in edges)


def test_attach_empty_namespace():
    assert attach(Namespace(topic="空"), dry_run=True) == []


def test_default_min_score_is_sane():
    assert 0.0 < DEFAULT_MIN_SCORE < 1.0
