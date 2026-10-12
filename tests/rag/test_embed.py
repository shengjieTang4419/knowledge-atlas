"""L2 embedding · 验收测试（契约，零依赖）。

运行：uv run pytest tests/rag/test_embed.py -q
"""
from app.rag.embed import cosine_similarity, embed


def test_cosine_orthogonal():
    assert abs(cosine_similarity([1, 0], [0, 1])) < 1e-9


def test_cosine_same_direction():
    assert abs(cosine_similarity([1, 2, 3], [2, 4, 6]) - 1.0) < 1e-9


def test_cosine_opposite():
    assert abs(cosine_similarity([1, 0], [-1, 0]) + 1.0) < 1e-9


def test_cosine_zero_vector_raises():
    for a, b in [([0, 0], [1, 0]), ([1, 0], [0, 0])]:
        try:
            cosine_similarity(a, b)
            raise AssertionError("零向量应抛 ValueError")
        except ValueError:
            pass


def test_cosine_dimension_mismatch_raises():
    try:
        cosine_similarity([1, 2], [1, 2, 3])
        raise AssertionError("维度不一致应抛 ValueError")
    except ValueError:
        pass


def test_embed_stub_shape_and_determinism():
    v = embed(["苹果", "香蕉", "苹果"])
    assert len(v) == 3
    assert all(isinstance(x, list) for x in v)
    assert len({len(x) for x in v}) == 1, "所有向量应同维度"
    assert v[0] == v[2], "同一文本应同一向量（确定性）"
    assert v[0] != v[1], "不同文本应不同向量"


TESTS = [
    test_cosine_orthogonal,
    test_cosine_same_direction,
    test_cosine_opposite,
    test_cosine_zero_vector_raises,
    test_cosine_dimension_mismatch_raises,
    test_embed_stub_shape_and_determinism,
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
