#!/usr/bin/env node
/**
 * Electron 启动包装器：清掉宿主注入的 `ELECTRON_RUN_AS_NODE` 再起 electron-vite。
 *
 * 为什么必须这样（实测根因）：
 *   DSH / VS Code 等**基于 Electron 的宿主**会把 `ELECTRON_RUN_AS_NODE=1` 注入子进程环境。
 *   该变量会让 electron 二进制**退化成纯 Node**：此时 `require('electron')` 解析到的是
 *   npm wrapper（导出二进制路径字符串），主进程第一行就崩：
 *       TypeError: Cannot read properties of undefined (reading 'isPackaged')
 *   症状极易误判为「代码写错」—— 实测在纯净目录下同样复现，才定位到是环境变量。
 *
 * 用法：node scripts/electron-run.mjs dev|preview|build
 */
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const bin = join(here, '..', 'node_modules', '.bin', 'electron-vite')

if (!existsSync(bin)) {
  console.error('[electron-run] 未找到 electron-vite，请先 pnpm install')
  process.exit(1)
}

const env = { ...process.env }
const polluted = 'ELECTRON_RUN_AS_NODE' in env
delete env.ELECTRON_RUN_AS_NODE
if (polluted) {
  console.log('[electron-run] 已清除宿主注入的 ELECTRON_RUN_AS_NODE（否则 electron 会退化为 Node）')
}

const child = spawn(bin, process.argv.slice(2), { stdio: 'inherit', env })
child.on('exit', code => process.exit(code ?? 0))
