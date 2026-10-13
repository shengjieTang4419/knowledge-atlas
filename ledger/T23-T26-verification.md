# T23–T26 验证证据 · 可信源拆两层 + 搜索历史（五期）

## 验收结果（实测）
- **pytest**：150 passed（新增/改造集中在 `test_settings_search.py` 与 `test_cli.py`）
- **mypy --strict**：19 文件 0 错 · **ruff**：全过
- **前端门禁**：`pnpm type-check` / `pnpm format:check` / `pnpm build` 全过
- **渲染冒烟**：无头浏览器跑打包产物 + IPC 替身，7 项交互通过、控制台 0 错（见下）

## 需求 → 实现

| 唐的反馈 | 落点 |
|---|---|
| 「搜过的 topic 要持久化，左侧搜索之下要能看到历史」 | `settings.record_search/load_history/clear_history`（落 `data/settings/settings.json` 的 `history`）+ 侧栏历史列表（点即回搜） |
| 「可信源应该是 GitHub 这种泛化的，不是具体哪个文件——否则会有很多很多零散的可信源，没有价值」 | `Source`（平台级，id=宿主域名） / `SourceEntry`（文件级）两层；`normalize_platforms` 按域名归一 |

## 端到端实测（真机，含真实模型）

### 1) AI 判定 → 两层收纳（关键诉求）
```
uv run python -m app.cli search "Kubernetes 调度器原理"
可信源 2 个平台 · 条目 5 条
  [规范] Kubernetes 官方文档  (auto)  https://kubernetes.io/docs/
  [源码] GitHub  (auto)  https://github.com/
    · Kube-scheduler  → https://kubernetes.io/docs/concepts/scheduling-eviction/kube-scheduler/
    · Scheduling Framework  → …/scheduling-framework/
    · Assigning Pods to Nodes  → …/assign-pod-node/
    · schedule_one.go  → https://github.com/kubernetes/kubernetes/blob/master/pkg/scheduler/schedule_one.go
    · Scheduling framework plugins  → …/scheduler/framework/plugins
```
**5 个文件只收敛成 2 个可信源**（github.com 命中内置平台，名字保持「GitHub」；kubernetes.io 新收录）。

### 2) 缓存命中（连 L1 拆词都不再调模型）
```
$ time uv run python -m app.cli search "Kubernetes 调度器原理"     # 同主题第二次
real  0m0.087s
```
关键词直接取自模块里存的那份；对照首次搜索（走 orient + sourcing 两次模型调用）。

### 3) 旧数据读时迁移（无数据丢失，且当场收敛）
`data/settings/settings.json` 旧的 `sources`（平台与文件混体）→ `items` + 全局平台注册表：
```
RAG 模块：2 篇 arXiv 论文  →  1 个平台 arxiv.org + 2 条条目
Embedding 模块：2 条 stanford 站点 →  1 个平台 web.stanford.edu
```

### 4) 历史持久化
```
uv run python -m app.cli history
  2026-10-12T21:29:30+08:00  向我详情介绍一下RAG  （4 个平台）
```
同主题再搜 = 顶到最前不新增；上限 20；`draft` 预演传 `record_history=False`（零副作用，有用例）。

## 变更清单
| 文件 | 动作 |
|---|---|
| `app/models.py` | `Source` 收窄为平台级（+`home`/`id`/`origin`，去 `locator`）；+`SourceEntry` |
| `app/settings.py` | 模块 `sources`→`items`；+平台注册表（`load/register/remove_platforms`、`platform_id`/`host_of`）；+历史（`record_search`/`load_history`/`clear_history`）；+`_migrate`（两种旧格式）；`_write_section` 分段写 |
| `app/layers/retrieve.py` | 重写：两层产物 + `normalize_platforms` 域名归一 + 悬空平台兜底 + 缓存命中跳过 L1 |
| `app/layers/topology.py` | 抽取 prompt 用 `Source.home` |
| `app/cli.py` | 契约改两层；+`history`/`history-clear`/`platforms`/`platform-add`/`platform-remove`/`entry-add`/`entry-remove`（`source-add`/`source-remove` 退役） |
| `config/sources.yml` | `domains[].sources` → 顶层 `platforms` + `domains[].items`（id 取域名） |
| `prompts/sourcing.md` | 判据改「平台 + 条目」两层 |
| `frontend/src/shared/ipc.ts` | `TrustedSource`/`SourceEntry`/`HistoryItem`；IPC 通道与 `AtlasApi` 同步 |
| `frontend/src/{main/cli.ts,main/ipc.ts,preload/index.ts,renderer/src/api/index.ts}` | 契约转发（含 `historyList`/`platformsList`/`entryAdd`…） |
| `frontend/.../stores/atlas.ts` | +`history` + `loadHistory`/`clearHistory` |
| `frontend/.../App.vue` | 侧栏「搜索」下方历史列表（命中/未命中色点、清空、点击回搜） |
| `frontend/.../views/SearchView.vue` | 两层展示（可信源平台 → 具体条目）+ `?topic=` 回搜 |
| `frontend/.../views/ReviewView.vue` | 头部计数改「N 个平台 · M 条条目」 |
| `frontend/.../components/SourceSettings.vue` | 重写：可信源（平台）区 + 主题模块（条目）区 |
| `tests/{test_settings_search.py,test_cli.py}` | 改造 + 新增（迁移/归一/历史/CLI 契约） |
| `plan.md` / `status.md` / `docs/architecture.md` / `CHANGELOG.md` / `README_CN.md` | 同步当前架构 |

## 渲染冒烟（**非 Electron 真机**：本地静态服务 + IPC 替身）

桌面窗口需宿主手动 `make app`（本仓约定），故这里用 `frontend/out/renderer` 产物 + 一个
只读 IPC 替身（接口照 `shared/ipc.ts` 契约）在无头浏览器里跑通**渲染与交互**，
覆盖 Electron 主进程/IPC 那一层之外的全部前端逻辑：

| 交互 | 断言 | 结果 |
|---|---|---|
| 进搜索页 | 侧栏「搜索」下方出现 3 条历史（含未命中项） | ✓ |
| 点历史项 | 回搜该主题并渲染「可信源 2 个平台 / 具体条目 3 条」两层 | ✓ |
| 手动搜索 | 输入 + 点「搜索」→ 两层结果 + 「已自动收录」提示 | ✓ |
| 条目归属 | 每条显示所属平台名，locator 抽出的 URL 是真链接 | ✓ |
| 清空历史 | 历史区变「搜过的主题会留在这里」 | ✓ |
| 设置 → 可信源 | 平台区（含「内置 / AI 收录」标记与 id）+ 主题模块区（条目、加条目表单） | ✓ |
| 控制台 | `window.onerror` / `unhandledrejection` | **0 条** |

截图：`ledger/render-search-two-layer.png`（搜索页两层）、`ledger/render-source-settings.png`（设置页两区）。

## 未做（诚实登记）
- **Electron 真机 E2E 未跑**（桌面窗口需宿主手动 `make app`）；前端过了 type-check / format / build
  三道门禁 + 上面的渲染冒烟，**主进程 IPC 真调 Python 这一环未在真机验证**。
- 冒烟里发现的真问题已修：保存平台后界面显示 `id —`（同名同站会归入已有平台，返回列表里找不到原名）
  → `platform-add --json` 改为回报**归一后那条**（`{platform, platforms}`），界面据此说实话
  （「与已有平台同站，已归入 GitHub」），并加 CLI 契约用例钉死。
