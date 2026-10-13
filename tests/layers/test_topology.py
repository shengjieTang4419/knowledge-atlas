"""L3 层验收：wiki 解析 → 实体 / 关系 / 对齐（离线确定性路径）。"""
from app.layers.topology import (
    WIKI_DIR,
    all_entities,
    entity_domains,
    load_namespace,
    normalize,
    topic_matches,
    write_entity_cards,
)
from app.models import Entity, Namespace, Relation


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


def test_write_entity_cards_roundtrip(tmp_path):
    """写卡 → 卡文件带 frontmatter/一句话/关系链接；已存在不覆盖。"""
    ns = Namespace(
        topic="测试主题",
        entities=[
            Entity(name="A 实体", type="概念", one_line="A 的一句话"),
            Entity(name="B 实体", type="机制", one_line="B 的一句话"),
        ],
        relations=[Relation(src="A实体", dst="B实体", type="递进")],
    )
    written = write_entity_cards(ns, ns.entities, notes_dir=tmp_path)
    assert set(written) == {"A实体", "B实体"}
    a_text = (tmp_path / "A实体.md").read_text(encoding="utf-8")
    assert "领域: 测试主题" in a_text
    assert "类型: 实体·概念" in a_text
    assert "# A 实体" in a_text
    assert "## 一句话" in a_text and "A 的一句话" in a_text
    assert "→ [[B实体]]" in a_text, "A 指向 B 的关系链接应写入"
    b_text = (tmp_path / "B实体.md").read_text(encoding="utf-8")
    assert "← [[A实体]]" in b_text, "B 的入边应是 ← A"


def test_write_entity_cards_skips_existing(tmp_path):
    """已存在的卡不覆盖（保护人工编辑）。"""
    path = tmp_path / "已存在实体.md"
    path.write_text("人工内容，别动", encoding="utf-8")
    ns = Namespace(topic="t", entities=[Entity(name="已存在实体", type="概念", one_line="x")])
    assert write_entity_cards(ns, ns.entities, notes_dir=tmp_path) == []
    assert path.read_text(encoding="utf-8") == "人工内容，别动"
