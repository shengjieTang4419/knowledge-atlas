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
│   ├── models.py     # Source(平台) / SourceEntry(条目) / Entity / Relation / Namespace / Edge / Profile
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
| L1 | `layers/topic.py` | str → list[str] | — | ✅ |
| L2 | `layers/retrieve.py` | keywords → list[Source]（平台）+ list[SourceEntry]（条目） | `config/sources.yml` + `data/settings/settings.json` | ✅ |
| L3 | `layers/topology.py` | sources → Namespace | `data/wiki/` | ✅ |
| L4 | `layers/graph.py` + `layers/mechanism.py` | Namespace → list[Edge] + list[MechanismCard] | `data/graph/edges.md` + `data/mechanism/cards.md` | ✅ |
| L5 | `layers/profile.py` | events → Profile | 待定 | ✅（基础版） |
| 内核 | `rag/{chunker,bpe,embed,fuse}.py` | 契约先行（`tests/rag/`） | — | ✅ |

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

**三期任务卡（审核流：搜索 → 预览 → 人为审核 → 写入，2026-10-12 立项）**：

| # | 任务 | 交付物 | 验收 | 依赖 | 状态 |
|---|---|---|---|---|---|
| T17 | 审核流后端 | `graph.plan()`（纯计算）+ `topology.write_entity_cards()` + CLI `draft`/`commit`（JSON 契约） | `tests/test_cli.py` 全绿；`commit` 幂等 | T16 | ✅ |
| T18 | 审核页 + 入口 | `frontend/.../ReviewView.vue` + `SearchView` 生成按钮 + IPC `draftTopic`/`commitDraft` | `pnpm type-check` / `pnpm build` 过；真机 E2E 见 `status.md` 待办 | T17 | ✅ |

**四期任务卡（AI 资源层与检索准确性，2026-10-12 立项）**——由一次真实排查立项（搜「transform」拿到 RAG 的源、预览报「模型没抽出实体」）：

| # | 任务 | 交付物 | 验收 | 依赖 | 状态 |
|---|---|---|---|---|---|
| T19 | LLM 资源层·有界降级 | `llm.py` 多家 provider + `LLM_CHAIN_*` 有序降级链 + `LLM_MAX_ATTEMPTS` 有界；降级可见（`last_llm_route`/`last_llm_degraded`） | `tests/test_llm.py` 全绿；真机实测链首 503 自动换家 | T18 | ✅ |
| T20 | 检索误命中与缓存键 | `settings.matches_keywords`（ASCII 整词 / 中文子串）+ `settings.find_module`（topic 即缓存键） | `tests/test_settings_search.py` 全绿；`transform`/`ai` 不再误命中 | — | ✅ |
| T21 | 失败可见（治本） | `llm.last_llm_error()` + `draft` 载荷 `llmError`/`llmRoute`/`llmDegraded` + 审核页区分「调用失败」与「模型没给」 | `tests/test_cli.py`；审核页文案随 `llmError` 分支 | T19,T20 | ✅ |
| T22 | 模型配置进界面（系统配置弹层） | `settings` 读写 `data/settings/llm.json`（`.env` 只播种；明文 Key 不回传、支持 `apiKeyEnv` 引用）+ CLI `llm-config`/`llm-config-save`/`llm-probe` + **右下齿轮弹层**（Provider 增删改 / 链排序 / MoA 开关 / 测试连通） | `tests/test_llm_settings.py` 全绿；`pnpm type-check` + `format:check` 过；真机 `llm-probe` 出结论 | T19,T21 | ✅ |

**二期任务卡（L4 机制卡改造，2026-10-11 立项）**——见上 T12–T16。核心变更：`借鉴` 边退役，改由「机制卡 + 应用边」承载，类比退化为「共享同一张卡」的涌现查询（`mechanism.analogies_of`）。

**五期任务卡（可信源拆两层 + 搜索历史，2026-10-12 立项）**——由唐的两条反馈立项：
①「搜过的 topic 要持久化，左侧搜索之下要能看到历史」；②「可信源应该是 GitHub 这种泛化的/哪个平台，
不是具体哪个文件——否则会有很多很多零散的可信源，没有价值，这个要拆开来」。

| # | 任务 | 交付物 | 验收 | 依赖 | 状态 |
|---|---|---|---|---|---|
| T23 | 可信源拆两层 | `models.Source`（平台级：id=宿主域名）+ `models.SourceEntry`（条目：title/source/locator/note）；`settings.TrustedModule.items`；平台全局注册表（`load/register/remove_platforms`）；旧数据迁移（sources → items + platforms） | `tests/test_settings_search.py` 全绿（含迁移与幂等） | T22 | ✅ |
| T24 | 平台归一（治本防「零散」） | `retrieve.normalize_platforms`：按 locator 宿主域名归并平台、解析条目归属、悬空平台就地兜底；无条目支撑的平台直接丢 | 「3 篇 arXiv 论文 → 1 个平台 + 3 条条目」用例全绿 | T23 | ✅ |
| T25 | 搜索历史持久化 | `settings.record_search/load_history/clear_history`（同文件分段写，互不覆盖）+ `search_topic(record_history=…)` + CLI `history`/`history-clear` | 去重/上限/预演零副作用/写模块不抹历史，用例全绿 | T23 | ✅ |
| T26 | 界面两层与历史入口 | 侧栏「搜索」下方历史列表（点即回搜）+ 搜索页「可信源（平台）→ 具体条目」两层展示 + 设置页平台/条目分区管理 + IPC 契约（`historyList`/`platformsList`/`entryAdd`…） | `pnpm type-check` + `format:check` + `build` 过 | T24,T25 | ✅ |

**验收证据**：`ledger/T1-T10-verification.md`（ruff / mypy strict / 49 单测 / 端到端实测）+ `ledger/T12-T16-verification.md`（二期）+ `ledger/T23-T26-verification.md`（五期）。

**降级说明（L2 级，已登记）**：未配 embedding/LLM 时，L4 召回降级为字面 Jaccard、判边降级为领域启发式；
跨域「借鉴」边离线态基本不产生（阈值门挡下），属正确行为。配 `.env` 后恢复 L0。

**降级说明（资源层，T19/T22）**：按每档位链的书写顺序逐个试，第一个给出可用 JSON 的即服务方；
一家坏了自动换下一家（`maxAttempts` 有界）。模式可选 `fallback`（逐个试）或 `moa`（都问一遍再融合）。
判据：超时/连不上/5xx/429/401/模型不存在/**空响应或非 JSON** → 继续降级；HTTP 400（自己的入参错）→ 立即止损。
降级不抛异常、不中断链路，但**必须可见**（`last_llm_route` / `last_llm_degraded`）。
配置**在界面上改**（右下 ⚙ → 模型），落 `data/settings/llm.json`；`.env` 只做播种，文件存在即为真源。

## 五、追溯矩阵

| 需求（spec） | 任务 | 落点 |
|---|---|---|
| 给 topic 知道学什么 | T5 | `app/layers/topic.py` |
| 找可信源 | T6 | `app/layers/retrieve.py` + `config/sources.yml` |
| 单 namespace 拓扑 | T7 + T1 | `app/layers/topology.py` + `app/rag/chunker.py` |
| 递进/借鉴判边 | T8 + T3 + T4 | `app/layers/graph.py` + `app/rag/{embed,fuse}.py` |
| 机制卡 / 应用边 / 类比涌现 | T12–T16 | `app/layers/mechanism.py` + `data/mechanism/cards.md` |
| 人工审核后才写入（预览 → 审核 → 落盘） | T17,T18 | `app/cli.py`（`draft`/`commit`）+ `frontend/.../ReviewView.vue` |
| 一家模型坏了不断链路 | T19,T21 | `app/llm.py`（`LLM_CHAIN_*` 有序降级 + 降级可见） |
| 「可信源找到了」必须真找到 | T20 | `app/settings.py`（`matches_keywords` / `find_module`） |
| 可信源是平台（GitHub 这种），不是零散文件 | T23,T24 | `app/models.py`（Source/SourceEntry）+ `app/layers/retrieve.py`（`normalize_platforms` 域名归一） |
| 搜过的 topic 持久化，左侧搜索下方可见 | T25,T26 | `app/settings.py`（`record_search`/`load_history`）+ `frontend/.../App.vue` 历史列表 |
| 模型配置可运维（换家/调链/开 MoA 不用改文件重启） | T22 | 右下 ⚙ 弹层 + `data/settings/llm.json`（`app/settings.py` 读写） |
| 图谱累积、快速挂载 | T8, T10 | `data/graph/edges.md` + `app/cli.py` |
| 画像反哺 | T9 | `app/layers/profile.py` |
