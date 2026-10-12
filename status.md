# status.md — 实时进度

## 分层定义（唐定义，勿改）
`topic 定向` → `检索层` → `拓扑层（单 namespace）` → `图谱层（多 topic 组合）` → `画像层（抽象认知习惯）`

## 总体状态：功能开发已跑通（T0–T11 全部 ✅）

| 层 | 模块 | 状态 | 说明 |
|---|---|---|---|
| L1 topic 定向 | `app/layers/topic.py` | ✅ | 分隔符切分；有 LLM 时用模型拆词 |
| L2 检索层 | `app/layers/retrieve.py` | ✅ | 四级查找：内置 → 用户模块 → **AI 判定并自动收录** → 提示配置 |
| L3 拓扑层 | `app/layers/topology.py` | ✅ | 解析 wiki → 实体/关系；实体键=文件名 stem；同名对齐 |
| L4 图谱层 | `app/layers/graph.py` + `app/layers/mechanism.py` | ✅ | 机制卡 + 应用边 + 递进边；借鉴边退役为「共享卡」涌现 |
| L5 画像层 | `app/layers/profile.py` | ✅ | 基础版：主题分布 / 关系偏好 / 活跃度 |
| 内核 nanoRAG | `app/rag/*.py` | ✅ | chunker / bpe / embed / fuse |
| LLM 客户端 | `app/llm.py` | ✅ | OpenAI 兼容 + 离线降级（不抛异常） |
| CLI | `app/cli.py` | ✅ | orient / sources / topology / attach / profile / **pipeline** / **view**（含 `--json`）|
| 视图层 | `app/view.py` | ✅ | data/ → 零依赖单文件 HTML（`deliverables/graph.html`） |
| 桌面端 | `frontend/` | ✅ | Electron 薄壳 + Vue3；真机端到端验证通过（见 `ledger/frontend-electron-verification.md`） |

**验收（实测）**：`ruff` 全过 · `mypy --strict` 17 文件 0 错 · `pytest` **58 用例全绿** · `pipeline` 端到端跑通 · 图谱页真实浏览器验证通过（16 节点/6 边/交互/过滤/双档宽度）。
证据：`ledger/T1-T10-verification.md`。

## 端到端实测

```
uv run python -m app.cli pipeline "Java 多线程 · 内存可见性"
```
L1 拆词 → L2 出 4 个可信源（规范/源码优先）→ L3 收窄到 3 实体 / 5 关系 → L4 挂 5 条递进边。
真实写盘后 `data/graph/edges.md` 由 4 条 → **8 条**，手工边完整保留。

## 降级状态（L2 级 · 已登记）

未配 `.env` 的 `EMBEDDING_*` / `LLM_API_KEY`，故：
- L4 召回：真向量 cosine → **降级为字面 bigram Jaccard**
- L4 判边：LLM 判边 → **降级为「同域→递进 / 跨域→借鉴」启发式**

影响：离线态跨域「借鉴」边基本不产生（被 `min_score` 阈值挡下），**属正确行为**（无真实语义时宁缺勿滥）。
配 `.env` 后自动恢复 L0 能力。

## 界面（Electron）

| 页面 | 内容 |
|---|---|
| 搜索主题（首页） | 输入 topic → 关键词 + 可信源；AI 判定后**自动收录**并提示；无匹配时提示去配置 |
| 设置 | 可信源**模块**：按 topic 分组，`AI 自动` / `手工` 分类筛选；新建模块、增删来源 |

设计要点（2026-10-07 定）：可信源按 topic 组织成模块，`origin` 区分自动收录/手工；
**模块即缓存** —— 搜过的主题第二次直接命中，不再调模型。

## 桌面端（Electron 薄壳）

- 结构：`frontend/`（electron-vite 三分离：main / preload / renderer）
- 原则：**壳无脑、脑在 app/** —— 壳只做开窗口 / 读 `data/` / 调 Python CLI
- 实测：`pnpm type-check` / `pnpm format:check` / `pnpm build` 全过；
  真机六页端到端通过（搜索 / 设置 / 图谱 16 节点·3 边 / 卡片 16 张 / CLI 调通 Python）
- 三个环境坑已内置解法（宿主注入 `ELECTRON_RUN_AS_NODE`、pnpm 11 镜像传参、
  生产态 `file://` 不可用）→ 详见 `frontend/README.md`

## 待办（下一阶段）

1. **配 `.env` 跑 L0 全能力**：填 `EMBEDDING_BASE_URL/API_KEY` + `LLM_API_KEY`，验证跨域借鉴边真实产生。
2. **L3 的 LLM 抽取**接上 `prompts/extraction.md`（当前离线走 wiki 解析）。
3. **L5 画像**深化（当前是确定性聚合；反哺判边未接）。
4. 唐审关系 schema 口味（`config/schema.yml`、`data/graph/edges.md`）。

## 二期（L4 机制卡改造，2026-10-11）

把 L4 从「实体级借鉴边」升级为「卡/实例两层 + 三种关系」：

- **机制卡** = 独立一等公民（`data/mechanism/cards.md`），抽象可迁移的「解法动作」；
- **三种关系** = 递进（is-a/contains 骨架，实体↔实体）+ 应用（applies-to 锚点，卡↔实体）+ 类比（涌现：两实体共享同一张卡，非边）；
- **借鉴边退役**：`edges.md` 的借鉴分区迁移为机制卡 + 应用边；
- 任务卡 T12–T16，见 `plan.md` 二期。

**✅ 一期已交付**（T12–T16 全绿）：pytest 90 passed · mypy strict 0 错 · ruff 全过；证据 `ledger/T12-T16-verification.md`。
`cards`/`analogies` 命令可用；`view` 渲染机制卡分组（18 节点 = 16 实体 + 2 卡）。

**待推进（二期/三期）**：RRF 接入 recall · 图游走多跳 · 升格闸门（应用边 ≥2 升格全局卡）· profile 注入 judge。

## 关键决策
- 分层顺序 = 唐定义（L1–L5）。
- 实体键 = 文件名 stem（Obsidian `[[链接]]` 语义），标题仅展示——不做对关系会全断。
- 关系 schema = 递进（竖·深度）+ 应用（锚点，卡↔实体）；**借鉴退役**，类比 = 共享同一张卡的涌现。
- cosine 只做召回；关系类型化（schema + LLM 判边）才是串联。
- 机制卡决定网的高度，不决定网的密度；网体 = 递进 + 应用。
- 与云枢 RAG 物理隔离、单向升格。
- Git：只 add 精确文件，不 commit 不 push。
