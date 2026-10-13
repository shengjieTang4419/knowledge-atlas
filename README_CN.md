# knowledge-atlas · 个人知识学习平台

给一个 topic → 找可信源 → 梳成单 namespace 拓扑 → 提炼**机制卡**挂进多 topic 图谱 → 画像反哺。

## 五层（唐定义）

```
L1 topic 定向 → L2 检索层 → L3 拓扑层（单 namespace）→ L4 图谱层（多 topic 组合）→ L5 画像层
```

## 核心概念：可信源两层（L2）

**可信源 = 平台级**（GitHub / arXiv / Oracle 官方文档：泛化出处、跨主题复用，全局一份）；
**条目 = 文件级**（某平台上具体哪个文件，挂在主题模块下）。id 取**宿主域名**，
所以同一个站无论名字怎么写都只算一个平台——这是「可信源不爆炸」的机制保证。

## 核心概念：卡/实例两层 + 三种关系（v2）

**机制卡** = 把可迁移的「解法动作」从语境中抽象出来的一等公民。

| 关系 | 是什么 | 例子 |
|---|---|---|
| `递进`（is-a/contains） | 实体 ↔ 实体，客观知识层级 | `juc → jvm → jmm` |
| `应用`（applies-to） | 卡 ↔ 实体，把抽象落到具体 | `TCC 卡 → 订单预扣` |
| 类比 | **涌现，非边** —— 两实体共享同一张卡即「一看就通」 | `InnoDB 刷盘 ↔ 定时任务批量写` |

机制卡决定网的高度（金线）；`递进` + `应用` 决定网的密度（网体）。

## 目录结构

```
knowledge-atlas/
├── app/
│   ├── models.py          # Source(平台) / SourceEntry(条目) / Entity / Relation / Namespace / Edge / MechanismCard / Profile
│   ├── cli.py             # 薄入口
│   ├── layers/            # topic · retrieve · topology · graph · mechanism · profile
│   ├── rag/               # nanoRAG 内核：chunker · bpe · embed · fuse
│   ├── llm.py             # OpenAI 兼容客户端 + 离线降级
│   └── view.py            # data/ → 单文件 HTML 图谱
├── config/                # sources.yml · schema.yml
├── prompts/               # sourcing · extraction · relation_typing · mechanism_extraction
├── data/                  # wiki/（双链卡）· graph/edges.md · mechanism/cards.md
├── docs/                  # architecture.md · architecture-design.html · architecture-review.html
├── frontend/              # Electron 薄壳 + Vue3
├── tests/                 # 镜像 app/
└── constitution / spec / plan / status / CHANGELOG / ledger
```

## ⚠ 环境边界（先看这条）

| 干什么 | 在哪跑 | 为什么 |
|---|---|---|
| Python 五层（lint / test / CLI / view） | **容器内** | uv / ruff / mypy / pytest 都在容器里 |
| 前端门禁（类型检查 / 构建） | 容器内也行 | 不需要窗口 |
| **桌面窗口（`make app`）** | **必须宿主 macOS** | Electron 是 GUI 程序；容器是 Linux VM，没有显示器接窗口 |

## 配置 AI（可选，但推荐）

```bash
cp .env.example .env      # 填 LLM_API_KEY / LLM_BASE_URL
```

- `.env` 由 `app/config.py` 自动 `load_dotenv`（**不覆盖**已 export 的同名变量）；
- 不配也能用：整条链路退化到离线确定性路径（无 LLM 不抽卡、判边走同域启发式）。

## 怎么跑（容器内开发）

```bash
make lint        # ruff + mypy --strict
make test        # pytest
make test-rag    # 只跑 nanoRAG 四层契约（快）
make run ARGS="orient 'Java 多线程'"     # CLI 入口
make dev         # 查看 CLI 帮助
```

## 看图谱 / 机制卡（视图层）

```bash
uv run python -m app.cli view                          # -> deliverables/graph.html（浏览器打开）
uv run python -m app.cli cards                         # 列出机制卡
uv run python -m app.cli analogies "InnoDB 刷盘策略"     # 查类比涌现
```

零依赖单文件 HTML：从 `data/wiki/` + `data/graph/edges.md` + `data/mechanism/cards.md` 生成，
支持点节点看卡片、按「递进/应用」过滤、机制卡独立分组；未建卡的跨域端点显式列出（不静默丢边）。

## 桌面端（Electron 薄壳）

**必须在宿主 macOS 终端**（不是在容器里）：

```bash
make app          # = cd frontend && pnpm dev
```

**壳无脑、脑在 `app/`**：主进程只做开窗口 / 读 `data/` / 调 Python CLI；五层逻辑一行不进 Node。

## 版本

- **v1.0.0**（2026-10-07）：五层骨架 + `递进/借鉴` 两条边 + nanoRAG 内核 + Electron 壳
- **v2.0.0**（2026-10-11）：L4 重构为卡/实例两层 + 三种关系，`借鉴` 边退役，机制卡升为一等公民

详见 `CHANGELOG.md`。

## 状态

见 `status.md`。
