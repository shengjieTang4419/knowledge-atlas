---
领域: Embeddings与向量数据库
类型: 实体·模型
---

# word2vec

## 一句话
用「预测上下文」这个任务，让模型顺手学出每个词的向量。

## 是什么（骨架）
- 隐藏层权重矩阵 = 词向量表
- 输出层 = vocab_size 的 softmax
- 超参：min_count（最小词频）、size（向量维度）、workers

## 为什么重要
- 这是「从零理解词向量」的最小模型，nanoRAG 的先声

## 挂载（从零实现）
- `word2vec/word2vec_from_scratch.py`
- `word2vec/three_kingdoms_word2vec.py`（三国语料）
- `word2vec/query_similar.py`

## 待深挖
- [ ] CBOW 与 Skip-gram 的区别
- [ ] 负采样是怎么加速的
