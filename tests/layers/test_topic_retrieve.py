"""L1/L2 层验收：topic 定向 + 可信源检索（离线确定性路径）。"""
from app.layers.retrieve import find_sources, rank_sources
from app.layers.topic import orient
from app.models import Source


def test_orient_splits_by_separators():
    kws = orient("Java 多线程 · 内存可见性")
    assert "Java 多线程 · 内存可见性" in kws  # 整串保序在首位
    assert "Java" in kws and "多线程" in kws and "内存可见性" in kws


def test_orient_dedup_and_empty():
    assert orient("") == []
    assert orient("  ") == []
    kws = orient("AI,AI,深度学习")
    assert kws.count("AI") == 1


def test_find_sources_hits_registry_and_ranks():
    srcs = find_sources(orient("Java 多线程 · 内存可见性"))
    assert srcs, "应命中 config/sources.yml 的 java-concurrency 域"
    # 规范/源码 属最高可信度，必须排在博客之前
    types = [s.type for s in srcs]
    assert types[0] in {"规范", "源码"}
    assert types.index("博客") > 0


def test_find_sources_empty_keywords():
    assert find_sources([]) == []


def test_rank_sources_is_stable_and_truncates():
    raw = [
        Source(name="a", type="社区"),
        Source(name="b", type="规范"),
        Source(name="c", type="规范"),
        Source(name="d", type="书籍"),
    ]
    ranked = rank_sources(raw, limit=3)
    assert [s.name for s in ranked] == ["b", "c", "d"]  # 规范并列保持原序，社区被截掉
