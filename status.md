# status.md — 实时进度

## 分层定义（唐定义，勿改）
`topic 定向` → `检索层` → `拓扑层（单 namespace）` → `图谱层（多 topic 组合）` → `画像层（抽象认知习惯）`

## 总体状态：功能开发已跑通（T0–T11 全部 ✅）

| 层 | 模块 | 状态 | 说明 |
|---|---|---|---|
| L1 topic 定向 | `app/layers/topic.py` | ✅ | 分隔符切分；有 LLM 时用模型拆词 |
| L2 检索层 | `app/layers/retrieve.py` | ✅ | 四级查找：内置 → 用户模块 → **AI 判定并自动收录** → 提示配置；**两层：可信源（平台）+ 条目** |
| L3 拓扑层 | `app/layers/topology.py` | ✅ | 解析 wiki → 实体/关系；实体键=文件名 stem；同名对齐 |
| L4 图谱层 | `app/layers/graph.py` + `app/layers/mechanism.py` | ✅ | 机制卡 + 应用边 + 递进边；借鉴边退役为「共享卡」涌现 |
| L5 画像层 | `app/layers/profile.py` | ✅ | 基础版：主题分布 / 关系偏好 / 活跃度 |
| 内核 nanoRAG | `app/rag/*.py` | ✅ | chunker / bpe / embed / fuse |
| LLM 客户端 | `app/llm.py` | ✅ | 多家 provider + **有界自动降级链**（`LLM_CHAIN_*`）+ 离线降级（不抛异常）；降级可见 |
| CLI | `app/cli.py` | ✅ | orient / sources / topology / attach / profile / **pipeline** / **view** / **draft·commit**（审核流）/ **search·history·platforms·entry**（界面契约） |
| 视图层 | `app/view.py` | ✅ | data/ → 零依赖单文件 HTML（`deliverables/graph.html`） |
| 桌面端 | `frontend/` | ✅ | Electron 薄壳 + Vue3；真机端到端验证通过（见 `ledger/frontend-electron-verification.md`） |

**验收（实测）**：`ruff` 全过 · `mypy --strict` 19 文件 0 错 · `pytest` **150 用例全绿** ·
`make app-check`（type-check + format）与 `make app-build` 全过 · `pipeline` 端到端跑通 ·
图谱页真实浏览器验证通过（16 节点/6 边/交互/过滤/双档宽度）。
证据：`ledger/T1-T10-verification.md`、`ledger/T12-T16-verification.md`、`ledger/T23-T26-verification.md`。

## 可信源两层 + 搜索历史（2026-10-12）

**可信源 = 平台级**（GitHub / arXiv / Oracle 官方文档 这种泛化出处，全局一份、跨主题复用）；
**条目 = 文件级**（某平台上具体哪个文件，挂在主题模块下）。拆开的理由：混成一层，搜十个主题就攒出
几十条「可信源」，没有一条可复用——等于没有。

**收敛靠机制，不靠模型自觉**：`retrieve.normalize_platforms` 按 `locator` 的**宿主域名**归一
（`github.com` 怎么写都只算一个平台），可信度分级也定在平台上。搜「RAG」时模型给的 3 篇 arXiv 论文
→ **1 个可信源（arXiv）+ 3 条条目**。AI 只负责提条目，平台归 Python 收口。

- **可信源必须由条目支撑**：没条目的平台是噪声（归一后丢）；条目连域名都没有也丢（挂不上东西）；
  平台被删过导致引用悬空时，按条目域名**就地兜底补一个**（类型取最低档），不让整次搜索白跑。
- **三层数据落点**：内置平台与内置模块 `config/sources.yml`（入 git）；用户侧平台注册表、主题模块、
  搜索历史都在 `data/settings/settings.json`——**分段写**，谁写也不动另外两段。
- **搜索历史**：`{topic, at, matched, sourceCount}`，同主题只一条（再搜顶到最前），上限 20；
  记录点在 `retrieve.search_topic()`（CLI 与界面同一条路），`draft` 预演传 `record_history=False`
  保持零副作用。侧栏「搜索」正下方就是它，点了回搜。
- **旧数据自动迁移**（读时迁移、下次写盘落成新格式）：旧的 `sources`（平台与文件混体）拆成
  条目 + 平台，**同站当场收敛**（两条 arXiv 旧源 → 一个 `arxiv.org` 平台）。

## 审核流（搜索 → 预览 → 人为审核 → 写入，2026-10-12）

**不自动串联，人点一下才落盘**（守 constitution 原则 3「AI 铺路、人走」）：

| 步 | 入口 | 行为 |
|---|---|---|
| 1 搜索 | 搜索页 | L1 拆词 + L2 找可信源（**不写盘**，但记一条搜索历史） |
| 2 预览 | 搜索页「生成图谱 / 知识卡」→ 审核页 | `draft` 跑 L1→L4 预演，**零副作用**，列出实体 / 机制卡 / 边 |
| 3 审核 | 审核页（`/review`） | 逐项勾选，取消的**不写**；关系只保留两端实体都被选中的 |
| 4 写入 | 「确认写入」 | `commit` 落 `data/wiki/` 双链卡 + `edges.md` + `cards.md`（**幂等**，不覆盖人工已写卡） |

契约：`draft`/`commit` 恒吐 JSON（`frontend/src/shared/ipc.ts` 的 `DraftPreview` / `CommitResult`）；
`commit` 经临时文件接收审核后的草稿。

## AI 资源层（多家 provider · 有界降级 · 界面可配，2026-10-12）

一家模型坏了不该断掉整条链路。**配置在界面上改**（右下角 ⚙ → 模型）：Provider 增删、链路排序、
`fallback`/`MoA`模式、测试连通。落 `data/settings/llm.json`（不入 git）。

**`.env` 只做播种**——首次运行按 `.env` 生成配置，文件一旦存在即为唯一真源（成熟工具皆如此）：

```
LLM_DEFAULT_PROVIDER=ifans                  # 默认家（老键 LLM_BASE_URL/LLM_API_KEY 就是这家）
LLM_PROVIDER_<ID>_BASE_URL=…                # 追加家（缺 base_url 或缺 key 即不进池）
LLM_CHAIN_MAIN=gpt-plus,glm-flash,gpt-pro   # 按顺序试；写 moa: 前缀则该档位走融合
LLM_CHAIN_CHEAP=qwen-flash,glm-flash        # 轻任务（L1 拆词）
LLM_MAX_ATTEMPTS=3                          # 有界：链再长也不会无限打
```

判据（借 x_ai `app/ai/router.py`，**设施不借**——本仓单进程同步、无 Redis/多副本，探针/熔断/级联恢复没有触发者）：
超时 / 连不上 / 5xx / 429 / 401 / 模型不存在 / **空响应或非 JSON** → 换下一家；
HTTP 400（自己的入参错）→ **立即止损不降级**。降级不中断链路，但**必须可见**（审核页显示 `模型 <provider>/<model>`，降级时加 ⚠）。

**MoA（融合）**：链上都问一遍，列表取并集、标量取多数票（平票取链序靠前）。成本 ×N 由 `maxAttempts` 封顶。
与「人工审核」配套：模型放宽召回，人来筛。**测试连通是真调**——零成本 `GET /models` 会把「在清单里但调不通」的模型判成可用（实测 `gpt-flash` 在清单里却 503）。

**明文 Key 不回传**：读接口只给 `hasKey` + 脱敏提示，故保存时「留空 = 不改」；也可填 `apiKeyEnv` 引用环境变量，**密钥不落盘**。

**测试连通测的是已保存的配置**（探针按 `data/settings/llm.json` / `.env` 播种跑，看不到界面上未保存的改动）：
有未保存改动时按钮置灰并提示先保存。探针结论**按 `provider/model` 认，不按行号**——改了模型名那一行的旧结论即失效，
否则旧的 `❌ …/gpt-plus: HTTP 500` 会挂在新填的 `deepseek-flash` 下面，看上去像「改了没生效」。

真机实测：链首 `gpt-flash`（503）→ 自动换 `deepseek-flash`，**2.7s 成功**，`degraded=true`。
MoA 真机实测（`moa:gpt-plus,glm-flash`）：两家都答上，关键词并集去重，`route=ifans/gpt-plus+ifans/glm-flash`。

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
| 搜索主题（首页） | 输入 topic → 关键词 + **可信源（平台）+ 具体条目**两层；AI 判定后**自动收录**并提示；无匹配时提示去配置；命中后「生成图谱 / 知识卡」进审核页 |
| 侧栏「搜索」下方 | **搜索历史**（持久化）：命中点绿色、未命中点琥珀色，点了回搜该主题；「清空」一键清 |
| 审核（`/review`） | `draft` 预演结果 → 实体 / 机制卡 / 边逐项勾选 → 「确认写入」落 `data/`（**没勾的不写**） |
| 设置 | ① **可信源（平台）**：全局列表，新增/删除（内置不可删，改自 `config/sources.yml`）；② **主题模块**：按 topic 分组，`AI 自动` / `手工` 分类筛选；新建模块、增删条目（条目挂平台） |

设计要点：可信源按**平台**收敛（id 取宿主域名），条目按主题组织成模块；
**模块即缓存** —— 搜过的主题第二次直接命中，不再调模型。

## 桌面端（Electron 薄壳）

- 结构：`frontend/`（electron-vite 三分离：main / preload / renderer）
- 原则：**壳无脑、脑在 app/** —— 壳只做开窗口 / 读 `data/` / 调 Python CLI
- IPC 契约：载荷必须是**裸数据**。renderer 里 `ref(对象).value` 是响应式 Proxy，直接丢进 `ipcRenderer.invoke`
  会抛 `An object could not be cloned.`（实测），故带载荷的调用在 `api/index.ts` 桥层统一脱一次代理
- 实测：`pnpm type-check` / `pnpm format:check` / `pnpm build` 全过；
  真机六页端到端通过（搜索 / 设置 / 图谱 16 节点·3 边 / 卡片 16 张 / CLI 调通 Python）
- 三个环境坑已内置解法（宿主注入 `ELECTRON_RUN_AS_NODE`、pnpm 11 镜像传参、
  生产态 `file://` 不可用）→ 详见 `frontend/README.md`

## 待办（下一阶段）

0. **审核流真机 E2E**：宿主跑 `make app` → 搜索 → 生成 → 审核勾选 → 确认写入，看 `data/` 落盘与图谱刷新（代码门禁已过，真机未跑）。
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
