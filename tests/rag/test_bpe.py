"""L1 tokenizer · 验收测试（契约，零依赖）。

运行：uv run pytest tests/rag/test_bpe.py -q
全绿输出 PASS；任何一条失败在对应断言处报错。
"""
from app.rag.bpe import BPETokenizer


def test_untrained_is_plain_bytes():
    tok = BPETokenizer()
    assert tok.encode("abc") == [97, 98, 99]
    assert tok.decode([97, 98, 99]) == "abc"


def test_roundtrip_ascii():
    tok = BPETokenizer()
    tok.train("hello world hello world" * 20, vocab_size=280)
    s = "hello world"
    assert tok.decode(tok.encode(s)) == s


def test_roundtrip_chinese():
    tok = BPETokenizer()
    tok.train("我爱北京天安门，天安门上太阳升。" * 10, vocab_size=300)
    for s in ["我爱北京天安门", "天安门上太阳升"]:
        assert tok.decode(tok.encode(s)) == s, f"往返失败: {s}"


def test_roundtrip_mixed_and_rare():
    tok = BPETokenizer()
    corpus = "AI 深度学习 Embedding 向量数据库 RAG 知识图谱 nanoRAG"
    tok.train(corpus * 5, vocab_size=320)
    # 含训练语料里没见过的字符也要能无损往返
    assert tok.decode(tok.encode("Z 罕见字 X")) == "Z 罕见字 X"
    assert tok.decode(tok.encode(corpus)) == corpus


def test_train_grows_vocab():
    tok = BPETokenizer()
    target = 280
    # 用语料丰富的文本：24 次合并在「邻接对耗尽」之前能全部完成
    tok.train("the quick brown fox jumps over the lazy dog " * 40, vocab_size=target)
    assert len(tok.vocab) == target, f"训练后 vocab 应为 {target}，实际 {len(tok.vocab)}"
    assert len(tok.merges) == target - 256, "merges 应与 vocab 同步增长"


def test_train_stops_early_when_no_pairs():
    """契约允许「无可合并」时提前停：单一重复字符几轮就塌缩。"""
    tok = BPETokenizer()
    tok.train("aaaa", vocab_size=300)
    assert len(tok.vocab) <= 300
    assert tok.decode(tok.encode("aaaa")) == "aaaa"


def test_merge_compresses_repetition():
    tok = BPETokenizer()
    tok.train("你好" * 100, vocab_size=300)
    # "你好你好" = 12 个 UTF-8 字节；训练后应被合并成远少于 12 个 token
    n_ids = len(tok.encode("你好你好"))
    assert n_ids < 6, f"重复文本应被明显压缩，实际 {n_ids} 个 token"


TESTS = [
    test_untrained_is_plain_bytes,
    test_roundtrip_ascii,
    test_roundtrip_chinese,
    test_roundtrip_mixed_and_rare,
    test_train_grows_vocab,
    test_train_stops_early_when_no_pairs,
    test_merge_compresses_repetition,
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
