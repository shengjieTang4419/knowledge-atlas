"""L0 分块 · 验收测试（契约，零依赖）。

运行：uv run pytest tests/rag/test_chunker.py -q   （或 PYTHONPATH=src python3 tests/rag/test_chunker.py）
全绿输出 PASS；任何一条失败在对应断言处报错。

这些断言就是 chunk_markdown 的契约。实现到全 PASS 即过 L0。
"""
from app.rag.chunker import chunk_markdown


def test_empty_text():
    assert chunk_markdown("") == []
    assert chunk_markdown("   \n  ") == []


def test_heading_path_tracked():
    md = (
        "# 一级\n"
        "引言内容。\n\n"
        "## 二级\n"
        "正文 A。\n\n"
        "## 另一个二级\n"
        "正文 B。\n"
    )
    chunks = chunk_markdown(md, source="t.md")
    assert chunks, "不应返回空"
    assert chunks[0].heading_path == ["一级"]
    a = next(c for c in chunks if "正文 A" in c.text)
    assert a.heading_path == ["一级", "二级"]
    b = next(c for c in chunks if "正文 B" in c.text)
    assert b.heading_path == ["一级", "另一个二级"]


def test_source_and_seq():
    md = "# 标题\n\n正文。\n"
    chunks = chunk_markdown(md, source="foo.md")
    assert chunks[0].source == "foo.md"
    assert [c.seq for c in chunks] == list(range(len(chunks)))


def test_long_paragraph_split_with_overlap():
    long_text = "甲" * 1000
    chunks = chunk_markdown(long_text, max_chars=200, overlap=20)
    assert len(chunks) >= 5, f"1000 字符 / 200 每块 应切成 ≥5 块，实际 {len(chunks)}"
    for c in chunks:
        assert len(c.text) <= 200 + 20, f"块超长: {len(c.text)}"
    assert chunks[0].text[-20:] == chunks[1].text[:20], "相邻块应按 overlap 重叠"


def test_short_paragraph_not_split():
    md = "# T\n\n短内容。\n"
    chunks = chunk_markdown(md, max_chars=500)
    assert len(chunks) == 1


TESTS = [
    test_empty_text,
    test_heading_path_tracked,
    test_source_and_seq,
    test_long_paragraph_split_with_overlap,
    test_short_paragraph_not_split,
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
