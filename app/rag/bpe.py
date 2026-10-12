"""nanoRAG · L1 tokenizer（minbpe 风格 · byte-level BPE）。

契约（先读 test_bpe.py 再实现）：
1. 初始 vocab = 256 个单字节 token（id 0~255）。
2. train(text, vocab_size)：反复合并「出现最频繁的相邻 token 对」，直到 vocab_size 或无可合并。
   - 每次合并产生一个新 token（id 从 256 递增），记入 self.merges[(a, b)] = new_id。
3. encode(text)：text → utf-8 bytes → 按 merges 的 id 从小到大反复合并 → token ids 列表。
4. decode(ids)：token ids → 各自字节 → 拼回 utf-8 文本。往返必须无损（含中文）。

这是「理解用」层：看懂「文本 → token id」怎么发生。下游 nanoRAG 不强制用它（可用现成 embedding 自带的 tokenizer）。
"""

__all__ = ["BPETokenizer"]


class BPETokenizer:
    def __init__(self) -> None:
        self.vocab: dict[int, bytes] = {i: bytes([i]) for i in range(256)}  # id -> bytes
        self.merges: dict[tuple[int, int], int] = {}  # (a, b) -> new_id

    @staticmethod
    def _count_pairs(ids: list[int]) -> dict[tuple[int, int], int]:
        counts: dict[tuple[int, int], int] = {}
        for a, b in zip(ids, ids[1:], strict=False):
            counts[(a, b)] = counts.get((a, b), 0) + 1
        return counts

    @staticmethod
    def _merge_pair(ids: list[int], pair: tuple[int, int], new_id: int) -> list[int]:
        out: list[int] = []
        i = 0
        while i < len(ids):
            if i < len(ids) - 1 and ids[i] == pair[0] and ids[i + 1] == pair[1]:
                out.append(new_id)
                i += 2
            else:
                out.append(ids[i])
                i += 1
        return out

    def train(self, text: str, vocab_size: int = 276) -> None:
        """从语料学出 merges，直到 vocab_size 或无可合并。"""
        ids = list(text.encode("utf-8"))
        for i in range(max(0, vocab_size - 256)):
            counts = self._count_pairs(ids)
            if not counts:
                break
            # 最高频优先；并列时取字典序最小的 pair（保证确定性）
            pair = min(counts, key=lambda p: (-counts[p], p))
            new_id = 256 + i
            self.merges[pair] = new_id
            self.vocab[new_id] = self.vocab[pair[0]] + self.vocab[pair[1]]
            ids = self._merge_pair(ids, pair, new_id)

    def encode(self, text: str) -> list[int]:
        """text -> token ids。每次合并「merge id 最小」的现存 pair（minbpe 口径）。"""
        ids = list(text.encode("utf-8"))
        while len(ids) >= 2:
            counts = self._count_pairs(ids)
            pair = min(counts, key=lambda p: (self.merges.get(p, len(self.vocab)), p))
            if pair not in self.merges:
                break
            ids = self._merge_pair(ids, pair, self.merges[pair])
        return ids

    def decode(self, ids: list[int]) -> str:
        """token ids -> text。"""
        return b"".join(self.vocab[i] for i in ids).decode("utf-8", errors="replace")
