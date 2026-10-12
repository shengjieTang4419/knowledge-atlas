#!/usr/bin/env node
/**
 * 确保 Electron 二进制就位（跨平台、零依赖）。
 *
 * 为什么需要它（根因）：
 *   实测 pnpm 11 **不会**把 `.npmrc` 里的自定义键传给子进程 postinstall
 *   （`npm_config_electron_mirror` 为空），而 `@electron/get` 正是读它来决定下载源；
 *   于是 electron 自己的 postinstall 回落到 GitHub —— 国内/容器里会**静默卡死**。
 *
 * 做法：显式带上镜像环境变量，再调 electron 自带的 install.js。
 *   该脚本是幂等的（`isInstalled()` 为真即 `exit 0`），所以重复执行无副作用。
 */
import { spawnSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'

const require = createRequire(import.meta.url)

/** 可用 ELECTRON_MIRROR 覆盖（CI 换源时用） */
const DEFAULT_MIRROR = 'https://npmmirror.com/mirrors/electron/'

let electronDir = ''
try {
  electronDir = dirname(require.resolve('electron/package.json'))
} catch {
  // 未安装 electron（例如只装 prod 依赖）：不阻塞安装流程
  process.exit(0)
}

if (process.env.ELECTRON_SKIP_BINARY_DOWNLOAD) {
  process.exit(0)
}

const mirror = process.env.ELECTRON_MIRROR || DEFAULT_MIRROR
const result = spawnSync(process.execPath, [join(electronDir, 'install.js')], {
  stdio: 'inherit',
  env: { ...process.env, ELECTRON_MIRROR: mirror }
})

if (result.status !== 0) {
  console.error(
    `[ensure-electron] 下载失败。可手动重试：\n` +
      `  ELECTRON_MIRROR=${mirror} node node_modules/electron/install.js`
  )
  process.exit(result.status ?? 1)
}
