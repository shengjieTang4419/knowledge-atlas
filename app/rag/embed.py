"""nanoRAG · L2 embedding。

契约（先读 test_embed.py 再实现）：
1. cosine_similarity(a, b)：余弦相似度，纯函数。
   - 两向量维度不一致 → ValueError；任一为零向量 → ValueError。
2. embed(texts, *, backend="stub")：文本 → 向量列表。
   - backend="stub"：确定性占位实现（无外部依赖）：同一文本永远同一向量，不同文本向量不同，所有向量同维度。
   - 接真模型（BGE / text-embedding-3）时换 backend 或另行实现，函数签名不变。
"""
import hashlib
import math

__all__ = ["cosine_similarity", "embed"]

_STUB_DIM = 64


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """两向量夹角的余弦，值域 [-1, 1]。"""
    if len(a) != len(b):
        raise ValueError(f"维度不一致: {len(a)} vs {len(b)}")
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        raise ValueError("零向量没有夹角")
    return sum(x * y for x, y in zip(a, b, strict=True)) / (norm_a * norm_b)


def _stub_vector(text: str, dim: int = _STUB_DIM) -> list[float]:
    """确定性占位向量：同一文本恒等，不同文本（几乎必然）不同。"""
    out: list[float] = []
    counter = 0
    while len(out) < dim:
        digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
        for byte in digest:
            out.append(byte / 255.0 - 0.5)
            if len(out) == dim:
                break
        counter += 1
    return out


def embed(texts: list[str], *, backend: str = "stub") -> list[list[float]]:
    """文本 -> 向量。backend="stub" 为确定性占位，真模型换 backend。"""
    if backend == "stub":
        return [_stub_vector(t) for t in texts]
    if backend == "api":
        from app.llm import embed_texts  # 延迟导入：rag 层保持零外部依赖、可离线测

        return embed_texts(texts)
    raise ValueError(f"未知 backend: {backend}")
