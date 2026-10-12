# 桌面端（Electron 薄壳）验收证据

- 日期：2026-10-07
- 范围：`frontend/` 目录结构 + 端到端打通（Electron 真机运行，CDP 验证）
- 环境：Electron 33.4.11 / Node 22.23 / pnpm 11.22 / Vue 3.5 / Vite 5.4

## 验证门结果

| 门 | 命令 | 结果 |
|---|---|---|
| 类型检查 | `pnpm type-check`（vue-tsc + tsc） | **通过**（0 错） |
| 格式 | `pnpm format:check` | **All matched files use Prettier code style** |
| 构建 | `pnpm build` | main 5.7kB / preload 0.7kB / renderer 276kB + 4 个懒加载 chunk |
| 依赖安装 | `pnpm install` | 434 包，**无 IGNORED_BUILDS 警告** |
| Python 侧（未受影响） | `make lint` / `make test` | ruff 全过 · mypy 17 文件 0 错 · **60 用例全绿** |

## 端到端实测（真实 Electron + CDP 9228）

启动：`pnpm dev`（走 `scripts/electron-run.mjs`）；本次用打包产物 `electron .` 验生产态。

| 页面 | 断言 | 实测值 |
|---|---|---|
| 图谱 | target URL | `app://bundle/index.html#/graph` |
| 图谱 | 节点 / 边 / 领域框 | **16 / 3 / 2** |
| 图谱 | 未建卡边提示 | 2 个 chip（端点未建卡，设计允许） |
| 图谱 | 侧栏 footer | `实体 16 \| 边 3 \| 未建卡边 2` |
| 图谱 | 画布 | 原生 900×1072，容器可滚动，字号 13.5px 清晰 |
| 图谱 | 连线几何自检（端点落节点框边缘） | 6/6 通过，**0 悬空** |
| 卡片 | 分组 / 卡片数 | 2 组 / 16 张 |
| 卡片详情 | 路由 + 正文 | `#/cards/Embedding是什么`，标题正确，正文 364 字符 |
| 跑层 | IPC → Python CLI | `✓ uv run python -m app.cli orient …`，返回真实 JSON |
| 侧栏 | 仓库根定位 | `/Users/tangshengjie/workSpace/study/knowledge-atlas` |
| 全页 | 报错 | 无 |

**关键链路贯通**：Renderer → preload 白名单桥 → main IPC → `uv run python -m app.cli` → Python 五层。
即「壳无脑、脑在宿主」成立——界面里没有一个字的业务逻辑。

## 开发中定位并修复的真缺陷

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| 1 | Electron 主进程首行崩 `isPackaged` | 宿主注入 `ELECTRON_RUN_AS_NODE=1`，electron 退化成 Node（`require('electron')` 返回字符串）；**纯净目录同样复现**才定位到是环境变量 | `scripts/electron-run.mjs` 清变量后再起（dev/build/preview 全走它） |
| 2 | `ERR_PNPM_IGNORED_BUILDS` + 下载静默卡死 | pnpm 11 不传 `.npmrc` 的 `electron_mirror`（`@electron/get` 读不到）→ 回落 GitHub；且构建白名单在 pnpm 11 要写 `pnpm-workspace.yaml` | `scripts/ensure-electron.mjs` 显式带 `ELECTRON_MIRROR`；白名单迁到 `pnpm-workspace.yaml` |
| 3 | 窗口打开但页面空白 | `file://` 下 `<script type="module">`/CSS 被 webSecurity 判跨源而全部拒绝（resources 为空） | 注册 `app://` 自定义协议（standard+secure），不关 webSecurity |
| 4 | preload 类型检查失败 `Cannot find name 'window'` | 有段不可达的 fallback 用了 `window`，而 node 侧 tsconfig 无 DOM 类型 | 删死代码（恒开 contextIsolation，无需 fallback） |
| 5 | `@electron-toolkit/*` 加载崩 | `utils` 在模块顶层访问未就绪的 `electron.app`；`preload` 会透出 `ipcRenderer` 本体（攻击面大） | 两个包都移除，自己写 5 行（白名单只暴露本项目 API） |
| 6 | 图谱底部截断 / 分组被详情遮挡 | 窗口 1360 宽下主区仅 780px，而图谱 900×1072 | 窗口放大到 1500×1000 + 布局 flex 约束 + 画布容器滚动 |
| 7 | **图谱多出反向重复边**（图上绕行弧） | 拓扑层没解析行内箭头方向：`前置 ← [[JMM]]` 被建成 `volatile→JMM`，与 `JMM → volatile` 互为反向 | 按 `→`/`←` 定朝向；关系从 5 条降到 3 条干净链，并加 2 条方向断言钉死 |

## 视觉审核（interactive-html-explainer skill 要求）

送 `ifans_vision.py`（gpt-flash）审核截图，报了「~15/16 节点可见 + 2 条悬空线」。

**经程序化精测推翻**：16/16 节点均在可视区内（`outsideStage: []`），连线几何自检 6/6 通过。
模型把「⚠ 2 条边的端点尚未建卡」的提示横幅误读成了悬空线。
按用户「先取证再改」的规矩，**该判断不采信**；但据 skill 的缩放警告另修了字号问题（见 #6）。

## 遗留

- 打包（`electron-builder`）未跑：Python 运行时尚未随包，当前约定壳与仓库共存。
- 卡片正文为 `<pre>` 纯文本，未接 markdown 渲染。
