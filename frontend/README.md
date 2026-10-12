# knowledge-atlas 桌面端（Electron 薄壳）

## 定位：壳无脑，脑在宿主

这里**不做业务**。五层逻辑（topic 定向 / 检索 / 拓扑 / 图谱 / 画像）的唯一真相源是仓库根的 Python 包 `app/`。

壳只做三件事：

| 职责                       | 落点                |
| -------------------------- | ------------------- |
| 开窗口                     | `src/main/index.ts` |
| 读 `data/`（卡片）         | `src/main/data.ts`  |
| 调 Python CLI（图谱/五层） | `src/main/cli.ts`   |

> 这样换外壳（Tauri / 浏览器）时，业务零重写。

## 目录

```
frontend/
├── package.json / electron.vite.config.ts / electron-builder.yml
├── tsconfig.json → tsconfig.node.json（main+preload）/ tsconfig.web.json（renderer）
├── .npmrc（含 Electron 国内镜像）/ .prettierrc / .editorconfig
├── src/
│   ├── shared/ipc.ts        # ★ IPC 契约：通道名 + 类型（main/preload/renderer 共用）
│   ├── main/                # 主进程（Node 全权）
│   │   ├── index.ts         # 窗口生命周期
│   │   ├── paths.ts         # 仓库根定位（找含 data/wiki 的目录）
│   │   ├── data.ts          # 读卡片（fs）
│   │   ├── cli.ts           # 调 Python CLI + 字段映射
│   │   └── ipc.ts           # 通道注册
│   ├── preload/             # 白名单桥（contextBridge）
│   │   ├── index.ts
│   │   └── index.d.ts       # window.api 类型
│   └── renderer/            # Vue3（只做展示）
│       ├── index.html
│       └── src/
│           ├── main.ts / App.vue
│           ├── api/index.ts     # window.api 的类型化封装（组件不直接碰 window）
│           ├── router/          # hash 路由（生产态 file:// 下 history 会 404）
│           ├── stores/          # Pinia
│           └── views/           # GraphView / CardsView / CardView / CliView
└── resources/               # 打包图标
```

## IPC 契约（`src/shared/ipc.ts`）

| 通道               | 入参             | 出参                 | 数据来源                            |
| ------------------ | ---------------- | -------------------- | ----------------------------------- |
| `atlas:repo-root`  | —                | `string`             | 主进程定位                          |
| `atlas:graph-load` | —                | `GraphData`          | `python -m app.cli view --json`     |
| `atlas:cards-list` | —                | `CardMeta[]`         | `data/wiki/notes/*.md`              |
| `atlas:card-read`  | `key`            | `CardDetail \| null` | 同上                                |
| `atlas:cli-run`    | `args: string[]` | `CliResult`          | 仓库根 `uv run python -m app.cli …` |

字段命名边界：Python 侧是 `snake_case`（`one_line`），main 映射成前端的 `camelCase`（`oneLine`）——**契约以 Python 为准，外壳适配**。

## 开发

### 桌面窗口：必须在宿主 macOS 跑

Electron 是 **GUI 程序**，而 devcontainer 在 macOS 上是 **Linux VM** —— 窗口没有显示器接，
弹不出来。所以 `pnpm dev` 只能在宿主跑：

```bash
# 宿主 macOS 终端（不是容器里）
cd ~/workSpace/study/knowledge-atlas
make app            # 等价于 cd frontend && pnpm dev
```

### 非 GUI 任务：容器里也能跑

```bash
make app-check      # 类型检查 + 格式（容器内可）
make app-build      # 构建产物（容器内可）
```

容器内 `make app-install` 会自动带 `ELECTRON_SKIP_BINARY_DOWNLOAD=1`（省 100MB 且用不上）。

### 为什么 `frontend/node_modules` 挂了独立命名卷

宿主那份 `node_modules` 里是 **macOS 版 Electron 二进制**（Mach-O arm64）；
若容器在同一目录 `pnpm install`，会覆盖成 Linux 版并**弄坏宿主的桌面端**。
devcontainer 给 `frontend/node_modules` 挂了独立卷，两边互不干扰（与 `.venv` 同套路）。

**推论**：容器与宿主各自需要装一次前端依赖；改了 `package.json` 两边都要 `pnpm install`。

### 直接命令

```bash
cd frontend
pnpm install      # .npmrc 已配国内 Electron 镜像
pnpm dev          # 起 Electron + Vite HMR（宿主）
pnpm type-check   # vue-tsc + tsc
pnpm format       # prettier
pnpm build:mac    # 打包（electron-builder，宿主）
```

运行时定位仓库根：默认从 `frontend/` 向上找含 `data/wiki` 的目录；也可用环境变量覆盖：

```bash
KNOWLEDGE_ATLAS_ROOT=/path/to/knowledge-atlas pnpm dev
```

## 环境坑（实测，务必先看）

### 1. `ELECTRON_RUN_AS_NODE` 会让 electron 退化成 Node

**症状**：主进程第一行就崩 —— `TypeError: Cannot read properties of undefined (reading 'isPackaged')`；
更迷惑的是 `require('electron')` 返回的是**字符串**（npm wrapper 的二进制路径），不是 API 对象。

**根因**：DSH / VS Code 等**基于 Electron 的宿主**会向子进程注入 `ELECTRON_RUN_AS_NODE=1`。
实测在纯净空目录下用同一个 electron 二进制同样复现，才确认是环境变量而非项目配置。

**已内置解法**：`scripts/electron-run.mjs` 在起 electron-vite 前清掉该变量，
`pnpm dev` / `pnpm build` / `pnpm preview` 都走它。

### 2. pnpm 11 不把 `.npmrc` 自定义键传给 postinstall

**症状**：`pnpm install` 报 `ERR_PNPM_IGNORED_BUILDS`，或静默卡死（Electron 二进制下不来）。

**根因**：`@electron/get` 读 `npm_config_electron_mirror`，而 pnpm 11 不传 `.npmrc` 的
`electron_mirror`（实测该变量为空）→ 回落到 GitHub，国内/容器里会卡死。

**已内置解法**：`scripts/ensure-electron.mjs` 显式带 `ELECTRON_MIRROR` 调 electron 的
`install.js`（该脚本幂等，已装则秒退）。另外 pnpm 11 的构建白名单要写在
`pnpm-workspace.yaml` 的 `onlyBuiltDependencies`（`package.json` 的 `pnpm` 字段已失效）。

### 3. 生产态不能用 `file://` 加载渲染产物

**症状**：窗口打开、标题正确，但页面空白（`#app` 空）；`performance.getEntriesByType('resource')` 为空。

**根因**：`file://` 页面加载同目录的 `<script type="module">` 与 CSS 会被 webSecurity 判为跨源而全部拒绝。

**已内置解法**：注册 `app://` 自定义协议提供渲染产物（standard + secure，语义等同 http），
不关 webSecurity。见 `src/main/index.ts` 的 `serveRenderer()`。

## 安全基线

- `contextIsolation: true` + `nodeIntegration: false`：渲染进程拿不到 Node。
- 能力只通过 `preload` 的白名单 API 暴露（不暴露 `ipcRenderer` 本体）。
- 外链一律交给系统浏览器（`setWindowOpenHandler` 拒绝应用内开窗）。
- `index.html` 带 CSP。

## 待办

- 卡片正文目前是 `<pre>` 纯文本；要富渲染再引入 markdown 渲染器（保持零框架依赖优先）。
- 图谱画布保持**原生尺寸 + 容器滚动**（不做等比缩放）：实测缩到 0.79 倍时 13.5px 字号
  视觉只剩约 10.6px，缩放任一比例都会压字号。
- 打包时把 Python 运行时也带上（当前约定：壳与仓库共存，靠 `KNOWLEDGE_ATLAS_ROOT` 定位）。
