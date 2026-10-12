# 个人知识学习平台 · 技术方案（Plan）

> 定义**骨架**与任务卡。骨架 = 通用结构 + 五层模块契约。命名/目录/风格等细节自行决定，不在此列。

## 一、通用结构（对齐 `~/workSpace/work/x_ai`：`app/` 布局 + 容器内开发）

```
knowledge-atlas/
├── pyproject.toml / uv.lock / .python-version   # uv 管理（Python 3.12），单一真相源
├── Makefile / .pre-commit-config.yaml           # ruff + mypy --strict
├── .devcontainer/                               # 容器内开发（.venv 走命名卷）
├── .vscode/ .env.example .gitignore .dockerignore
├── README.md / IDEA.md / AGENTS.md / CHANGELOG.md
├── constitution.md / spec.md / plan.md / status.md
├── config/    sources.yml（可信源+分级）· schema.yml（实体+关系 schema）
├── prompts/    sourcing.md · extraction.md · relation_typing.md
├── app/              # 包（x_ai 惯例）
│   ├── models.py     # Source / Entity / Relation / Namespace / Edge / Profile
│   ├── config.py     # 读 config/
│   ├── cli.py        # 薄入口
│   ├── layers/       # topic · retrieve · topology · graph · profile
│   └── rag/          # chunker · bpe · embed · fuse（nanoRAG 内核）
├── tests/            # 镜像 app/（pytest，pythonpath="."）
├── data/             # wiki/（双链卡）· graph/edges.md（全局边）
├── docs/architecture.md
├── deliverables/platform-flow.html
└── ledger/
```

## 二、五层 → 模块映射

| 层 | 模块 | 输入 → 输出 | 落盘 | 状态 |
|---|---|---|---|---|
| L1 | `layers/topic.py` | str → list[str] | — | stub |
| L2 | `layers/retrieve.py` | keywords → list[Source] | `config/sources.yml` | stub |
| L3 | `layers/topology.py` | sources → Namespace | `data/wiki/` | stub |
| L4 | `layers/graph.py` + `layers/mechanism.py` | Namespace → list[Edge] + list[MechanismCard] | `data/graph/edges.md` + `data/mechanism/cards.md` | 改造中 |
| L5 | `layers/profile.py` | events → Profile | 待定 | stub |
| 内核 | `rag/{chunker,bpe,embed,fuse}.py` | 契约先行（`tests/rag/`） | — | 契约已交付 |

## 三、技术选型

- wiki：Markdown 双链 + Obsidian（阅读器），git 仓为真相源
- 实体关系抽取 / 判边：LLM，schema 人定（`config/schema.yml` + `prompts/`）
- 向量：现成 embedding 模型（BGE / text-embedding-3-small），**不自己训**
- 融合：RRF（只用排名，不用分数）
- 图存储：markdown 双链起步，重了再上 networkx / Neo4j

## 四、任务卡

| # | 任务 | 交付物 | 验收 | 依赖 | 状态 |
|---|---|---|---|---|---|
| T0 | 骨架 | 本文件 + 目录 + pyproject | `uv run pytest` 可收集用例 | — | ✅ |
| T1 | rag/chunker（L0 分块） | `app/rag/chunker.py` | `tests/rag/test_chunker.py` 全绿 | T0 | ✅ |
| T2 | rag/bpe（tokenizer） | `app/rag/bpe.py` | `tests/rag/test_bpe.py` 全绿 | T0 | ✅ |
| T3 | rag/embed（向量+余弦） | `app/rag/embed.py` | `tests/rag/test_embed.py` 全绿 | T0 | ✅ |
| T4 | rag/fuse（RRF） | `app/rag/fuse.py` | `tests/rag/test_fuse.py` 全绿 | T0 | ✅ |
| T5 | L1 topic.orient | `app/layers/topic.py` | `tests/layers/test_topic_retrieve.py` 全绿 | T0 | ✅ |
| T6 | L2 retrieve.find_sources | `app/layers/retrieve.py` | 命中注册表 + 按可信度排序 | T5 | ✅ |
| T7 | L3 topology | `app/layers/topology.py` | 收窄 namespace + 解析关系 + 实体对齐 | T6,T3 | ✅ |
| T8 | L4 graph（recall/judge/attach） | `app/layers/graph.py` | `tests/layers/test_graph.py` 全绿 | T7,T4 | ✅ |
| T9 | L5 profile（基础版） | `app/layers/profile.py` | `tests/layers/test_profile.py` 全绿 | T8 | ✅ |
| T10 | CLI 端到端串联 | `app/cli.py` | `pipeline` 一条命令跑通 topic→图谱 | T1–T8 | ✅ |
| T11 | LLM 客户端 + 离线降级 | `app/llm.py` | 无 key 时降级不抛异常 | — | ✅ |
| T12 | L4 契约扩展 | `app/models.py` + `config/schema.yml`（+`MechanismCard` + 应用边，退役借鉴边） | mypy strict 0 错 | T11 | ✅ |
| T13 | 机制卡模块 | `app/layers/mechanism.py`（load / upsert / extract / attach_cards / analogies_of） | `tests/layers/test_mechanism.py` 全绿 | T12 | ✅ |
| T14 | graph.py 改造 | judge 判「递进/应用」、attach 挂卡、recall 走卡空间 | `tests/layers/test_graph.py` 全绿 | T13 | ✅ |
| T15 | prompt + 数据 | `prompts/mechanism_extraction.md` + `data/mechanism/cards.md` 样例卡 | `load_cards` 能解析样例卡 | T13 | ✅ |
| T16 | 全链路镜像 | topology 抽卡 + cli/view + 迁移 `edges.md` 借鉴边 | pytest 全绿 + pipeline 端到端 | T14,T15 | ✅ |

**二期任务卡（L4 机制卡改造，2026-10-11 立项）**——见上 T12–T16。核心变更：`借鉴` 边退役，改由「机制卡 + 应用边」承载，类比退化为「共享同一张卡」的涌现查询（`mechanism.analogies_of`）。

**验收证据**：`ledger/T1-T10-verification.md`（ruff / mypy strict / 49 单测 / 端到端实测）+ `ledger/T12-T16-verification.md`（二期）。

**降级说明（L2 级，已登记）**：未配 embedding/LLM 时，L4 召回降级为字面 Jaccard、判边降级为领域启发式；
跨域「借鉴」边离线态基本不产生（阈值门挡下），属正确行为。配 `.env` 后恢复 L0。

## 五、追溯矩阵

| 需求（spec） | 任务 | 落点 |
|---|---|---|
| 给 topic 知道学什么 | T5 | `app/layers/topic.py` |
| 找可信源 | T6 | `app/layers/retrieve.py` + `config/sources.yml` |
| 单 namespace 拓扑 | T7 + T1 | `app/layers/topology.py` + `app/rag/chunker.py` |
| 递进/借鉴判边 | T8 + T3 + T4 | `app/layers/graph.py` + `app/rag/{embed,fuse}.py` |
| 机制卡 / 应用边 / 类比涌现 | T12–T16 | `app/layers/mechanism.py` + `data/mechanism/cards.md` |
| 图谱累积、快速挂载 | T8, T10 | `data/graph/edges.md` + `app/cli.py` |
| 画像反哺 | T9 | `app/layers/profile.py` |
