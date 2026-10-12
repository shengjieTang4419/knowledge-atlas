"""L4 机制卡层验收：卡读写 / 应用边 / 类比涌现（离线确定性路径）。"""
from app.layers.mechanism import analogies_of, attach_cards, load_cards, upsert_cards
from app.models import MechanismCard


def test_load_cards_parses_sample():
    cards = load_cards()
    assert cards, "data/mechanism/cards.md 应有样例卡"
    names = {c.name for c in cards}
    assert "攒批写" in names


def test_attach_cards_produces_apply_edges():
    cards = [MechanismCard(name="攒批写", cases=["InnoDB 刷盘策略", "定时任务批量写"])]
    edges = attach_cards(cards)
    assert len(edges) == 2
    assert all(e.type == "应用" for e in edges)
    assert {(e.src, e.dst) for e in edges} == {
        ("攒批写", "InnoDB 刷盘策略"),
        ("攒批写", "定时任务批量写"),
    }


def test_analogies_of_finds_shared_card():
    hits = analogies_of("InnoDB 刷盘策略")
    assert hits, "InnoDB 刷盘策略 应命中「攒批写」卡"
    card_names = {h["card"] for h in hits}
    assert "攒批写" in card_names
    for h in hits:
        if h["card"] == "攒批写":
            assert "定时任务批量写" in h["siblings"]


def test_analogies_of_unmatched_is_empty():
    assert analogies_of("一个不存在的实体") == []


def test_upsert_cards_merges_same_name(tmp_path):
    path = tmp_path / "cards.md"
    upsert_cards([MechanismCard(name="攒批写", mechanism="a", cases=["A"])], path)
    upsert_cards([MechanismCard(name="攒批写", mechanism="b", cases=["B"])], path)
    cards = load_cards(path)
    assert len(cards) == 1
    assert cards[0].cases == ["A", "B"], "同名卡 cases 应去重合并"
