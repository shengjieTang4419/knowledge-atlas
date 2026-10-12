---
领域: Embeddings与向量数据库
类型: 支柱·选型
---

# Embedding 模型

## 一句话
embedding 是「理解向量空间怎么工作」的层，但生产用现成模型，不自己训。

## 是什么（骨架）
- [[Embedding模型选择]]：语言 / 领域 / 成本 / 维度
- 维度直接影响性能与存储（hidden_size = embedding 维度）

## 关键判断
- 理解层：[[word2vec]] 从零（已在做）
- 生产层：现成模型（BGE / text-embedding-3-small）

## 待深挖
- [ ] 中文场景 BGE vs 英文场景的选择逻辑
