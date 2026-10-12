"""nanoRAG 内核：从零手写，Karpathy 风格（先暴力能跑，每行可解释）。

chunker（L0 分块）→ bpe（L1 tokenizer）→ embed（L2 向量）→ fuse（L4 RRF 融合）。
契约先行：每层有验收测试（tests/rag/），实现到全绿为过。
"""
