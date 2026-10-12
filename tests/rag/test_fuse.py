"""L4 融合 · 验收测试（契约，零依赖）。

运行：uv run pytest tests/rag/test_fuse.py -q
"""
from app.rag.fuse import reciprocal_rank_fusion as rrf


def test_empty():
    assert rrf([]) == []


def test_single_preserves_order():
    assert rrf([["a", "b", "c"]]) == ["a", "b", "c"]


def test_two_way_fusion_hand_computed():
    # k=60，手算：
    #   b: 1/61 + 1/62 = 0.03252
    #   c: 1/62 + 1/63 = 0.03200
    #   a: 1/61         = 0.01639
    #   d: 1/63         = 0.01587
    result = rrf([["a", "b", "c"], ["b", "c", "d"]], k=60)
    assert result == ["b", "c", "a", "d"], f"实际 {result}"


def test_stable_order_on_tie():
    # x、y 分数相同（1/61 + 1/62），应保持首次出现顺序 [x, y]
    assert rrf([["x", "y"], ["y", "x"]]) == ["x", "y"]


def test_id_missing_in_some_lists():
    # 某些 id 只出现在一条路里，也能正常参与融合
    result = rrf([["a", "b"], ["b", "c"]], k=1)
    # a: 1/2, b: 1/3+1/2, c: 1/3 -> b > a > c
    assert result == ["b", "a", "c"], f"实际 {result}"


TESTS = [
    test_empty,
    test_single_preserves_order,
    test_two_way_fusion_hand_computed,
    test_stable_order_on_tie,
    test_id_missing_in_some_lists,
]

if __name__ == "__main__":
    failed = 0
    for t in TESTS:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(TESTS) - failed}/{len(TESTS)} passed")
    exit(1 if failed else 0)
