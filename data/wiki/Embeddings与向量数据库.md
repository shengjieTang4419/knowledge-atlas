# Embeddings 与向量数据库（领域 MOC）

> L1 骨架 · 第一领域。概貌来自 9/9 课件 PDF，抓取只做挂载。

## 四大支柱
1. [[Embedding是什么]] — 概念：任何物体 → 向量
2. [[相似度与检索]] — 计算：余弦 + Top-K
3. [[Embedding模型]] — 选型：维度 / 语言 / 成本
4. [[向量数据库]] — 存储与索引

## 骨架拓扑
```mermaid
graph TD
  R[Embeddings 与向量数据库] --> A[Embedding是什么]
  R --> B[相似度与检索]
  R --> C[Embedding模型]
  R --> D[向量数据库]
  A --> A1[word2vec]
  A --> A2[词向量语义运算]
  B --> B1[余弦相似度]
  B --> B2[Top-K检索]
  C --> C1[Embedding模型选择]
  D --> D1[与传统数据库的区别]
  D --> D2[产品对比]
  D --> D3[导入与元数据]
  D --> D4[索引 HNSW/量化]
```

## 学习状态
- [ ] 骨架经唐审
- [ ] Q&A 深挖（提问式）
