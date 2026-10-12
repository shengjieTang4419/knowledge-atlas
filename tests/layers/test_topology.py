"""L3 层验收：wiki 解析 → 实体 / 关系 / 对齐（离线确定性路径）。"""
from app.layers.topology import WIKI_DIR, all_entities, entity_domains, load_namespace, normalize, topic_matches


def test_wiki_present():
    assert (WIKI_DIR / "notes").exists(), "data/wiki/notes 应存在"


def test_normalize_aligns_spaced_and_unspaced_names():
    assert normalize("JMM 内存模型") == normalize("JMM内存模型")


def test_topic_matches_is_forgiving():
    assert topic_matches("Java多线程", "Java多线程", "Java 多线程 · 内存可见性")
    # 字面匹配：靠「多线程」这段命中领域；不指望它做语义匹配（那要召回层）
    assert topic_matches("volatile", "Java多线程", "Java 多线程 · 内存可见性")
    assert not topic_matches("Embedding是什么", "Embeddings与向量数据库", "Java 多线程")


def test_load_namespace_narrows_to_topic():
    ns = load_namespace("Java 多线程 · 内存可见性")
    names = [e.name for e in ns.entities]
    assert 1 <= len(names) <= 5, f"应收窄到该 namespace，实际 {len(names)}"
    assert any("JMM" in n for n in names)
    assert all("Embedding" not in n for n in names), "不该混入 Embeddings namespace 的实体"


def test_relations_parsed_with_normalized_keys():
    ns = load_namespace("Java 多线程 · 内存可见性")
    assert ns.relations, "该 namespace 应有递进关系"
    for rel in ns.relations:
        assert rel.type in {"递进", "应用"}
        assert " " not in rel.src and " " not in rel.dst, "关系端点应用归一化键（去空格）"


def test_all_entities_excludes_moc():
    ents = all_entities()
    assert ents, "应有实体"
    assert all("MOC" not in e.name for e in ents.values()), "MOC 页不是实体"
    assert all("总览" not in e.name for e in ents.values())


def test_entity_domains_maps_every_entity():
    domains = entity_domains()
    assert domains, "应有领域映射"
    assert all(v for v in domains.values())


def test_relations_respect_arrow_direction():
    """`→` 是出边、`←` 是入边：不看方向会造出互为反向的重复边（实测图上多出绕行悬空弧）。"""
    ns = load_namespace("Java 多线程 · 内存可见性")
    pairs = {frozenset((r.src, r.dst)) for r in ns.relations}
    assert len(pairs) == len(ns.relations), f"存在反向重复边：{[(r.src, r.dst) for r in ns.relations]}"


def test_prerequisite_chain_direction():
    """JMM → volatile → MESI：前置在链上游（正是 spec 里的 T 型竖线）。"""
    ns = load_namespace("Java 多线程 · 内存可见性")
    edges = {(r.src, r.dst) for r in ns.relations}
    # 关系键走 normalize()（去空白 + 小写），与实体键同口径
    assert ("jmm内存模型", "volatile") in edges
    assert ("volatile", "jmm内存模型") not in edges, "反向边不该存在"
