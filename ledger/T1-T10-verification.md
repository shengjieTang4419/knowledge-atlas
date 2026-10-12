# T1–T10 实现与验收证据

- 日期：2026-10-07
- 范围：knowledge-atlas 功能开发（nanoRAG 四层内核 + 五层 + CLI 端到端）
- 环境：uv / Python 3.12.12（容器内开发口径）

## 验证门结果（命令可复现）

| 门 | 命令 | 结果 |
|---|---|---|
| 静态检查 | `uv run ruff check app/ tests/` | **All checks passed** |
| 类型契约 | `uv run mypy app/`（strict） | **Success: no issues found in 16 source files** |
| 单测 | `uv run pytest tests/ -q` | **49 passed in 0.06s** |
| CLI 冒烟 | `uv run python -m app.cli --help` | 6 个子命令（orient/sources/topology/attach/profile/pipeline） |
| 端到端 | `uv run python -m app.cli pipeline "Java 多线程 · 内存可见性" --dry-run` | L1→L4 全链路跑通 |

## 任务卡完成情况

| # | 任务 | 交付物 | 验收 | 状态 |
|---|---|---|---|---|
| T1 | L0 分块 | `app/rag/chunker.py` | `tests/rag/test_chunker.py` 6 用例全绿 | ✅ |
| T2 | L1 tokenizer | `app/rag/bpe.py` | `tests/rag/test_bpe.py` 7 用例全绿 | ✅ |
| T3 | L2 embedding | `app/rag/embed.py` | `tests/rag/test_embed.py` 6 用例全绿 | ✅ |
| T4 | L4 融合 RRF | `app/rag/fuse.py` | `tests/rag/test_fuse.py` 5 用例全绿 | ✅ |
| T5 | L1 topic.orient | `app/layers/topic.py` | 5 用例全绿 | ✅ |
| T6 | L2 retrieve | `app/layers/retrieve.py` | 命中注册表并按可信度排序 | ✅ |
| T7 | L3 topology | `app/layers/topology.py` | 收窄 namespace、解析关系、实体对齐 | ✅ |
| T8 | L4 graph | `app/layers/graph.py` | 召回阈值 + 判边 + 边读写 | ✅ |
| T9 | L5 profile | `app/layers/profile.py` | 聚合画像 + 事件读写 | ✅ |
| T10 | CLI 串联 | `app/cli.py` | pipeline 端到端 | ✅ |
| 附加 | LLM 客户端 | `app/llm.py` | OpenAI 兼容 + 离线降级（不发请求不抛异常） | ✅ |

## 端到端实测（真实数据，非 fixture）

```
$ uv run python -m app.cli pipeline "Java 多线程 · 内存可见性" --dry-run
== L1 topic 定向：Java 多线程 · 内存可见性
   关键词: Java 多线程 · 内存可见性、Java、多线程、内存可见性
== L2 检索层
   [规范] JSR-133 / JLS §17
   [源码] OpenJDK
   [书籍] Java 并发编程实战（Goetz）
   [博客] Doug Lea 并发文档
== L3 拓扑层
   实体 3  关系 5
== L4 图谱层
   合计新增 5 条
```

真实写盘（`attach` 非 dry-run）：`data/graph/edges.md` 由 4 条 → **8 条**，
手工边（InnoDB 刷盘 / 分布式缓存一致性）**完整保留**，新增 5 条 namespace 内部递进边。

## 开发过程中修复的真缺陷（验证门抓出）

1. **实体键错位**：wiki 标题「JMM 内存模型」带空格，而 Obsidian `[[链接]]` 按**文件名 stem** 解析 → 关系只解析出 1 条。修法：实体键 = 文件 stem，标题仅作展示。
2. **MOC 被当实体**：`data/wiki/*.md` 的 MOC 页混入实体表 → 修法：实体只取 `notes/`。
3. **召回配对错**：拿任意本方实体去判边 → 修法：配对「最像的一对」。
4. **离线召回是噪声**：哈希 stub 向量的余弦无语义 → 修法：离线降级为字面 bigram Jaccard + `min_score` 阈值门（宁缺勿滥）。
5. **topic 匹配过严**：「Java 多线程 · 内存可见性」匹配不到 `Java多线程` → 修法：按分隔符切段做宽松匹配。

## 降级记录（L2 级 · 已按 runbook 规则登记）

未配 `EMBEDDING_*` / `LLM_API_KEY` 时（当前状态）：

| 环节 | 全能力（L0） | 当前（L2 降级） |
|---|---|---|
| L4 召回 | 真向量 cosine | 字面 bigram Jaccard |
| L4 判边 | LLM 判边 + 理由 | 「同域→递进 / 跨域→借鉴」启发式 |

影响：跨域「借鉴」边在离线态基本不产生（被阈值挡下）——**这是正确行为**（无真实语义时宁缺勿滥）。
配置 `.env` 里的 embedding/LLM 后即恢复 L0 能力。

## 已知数据待办

- `data/graph/edges.md` 的 `InnoDB 刷盘策略 → 定时任务批量写` 两端尚未建卡（跨域节点，设计允许先挂名）。
- 手工边 `MESI缓存一致性协议 → 分布式缓存一致性` 的目标端亦未建卡。
