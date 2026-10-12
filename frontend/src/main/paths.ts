/**
 * 仓库根定位：找含 `data/wiki` 的目录。
 *
 * - 生产/自定义：`KNOWLEDGE_ATLAS_ROOT` 环境变量优先；
 * - 开发态：从 Electron appPath（frontend/）向上找几层。
 */
import { existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'

import { app } from 'electron'

let cached: string | null = null

export function repoRoot(): string {
  if (cached) return cached
  const env = process.env.KNOWLEDGE_ATLAS_ROOT
  if (env && existsSync(join(env, 'data', 'wiki'))) {
    cached = resolve(env)
    return cached
  }
  let dir = app.getAppPath()
  for (let i = 0; i < 5; i++) {
    if (existsSync(join(dir, 'data', 'wiki'))) {
      cached = dir
      return cached
    }
    const parent = dirname(dir)
    if (parent === dir) break
    dir = parent
  }
  cached = resolve(app.getAppPath(), '..')
  return cached
}

export function dataDir(): string {
  return join(repoRoot(), 'data')
}

export function notesDir(): string {
  return join(dataDir(), 'wiki', 'notes')
}

export function edgesPath(): string {
  return join(dataDir(), 'graph', 'edges.md')
}
