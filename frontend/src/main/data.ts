/**
 * 知识数据只读层：从 `data/` 读卡片（fs）。
 *
 * 图谱计算不在这里做——那是 Python 层的职责（见 cli.ts 的 `graphLoad`），
 * 避免同一套布局/对齐逻辑在 TS 里再实现一遍。
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

import type { CardDetail, CardMeta } from '../shared/ipc'
import { notesDir } from './paths'

const TITLE_RE = /^#\s+(.+?)\s*$/m
const ONELINE_RE = /^##\s*一句话\s*\n+(.+?)\s*$/m
const FM_RE = /^---\s*\n([\s\S]*?)\n---\s*\n/

function frontmatter(text: string): Record<string, string> {
  const m = FM_RE.exec(text)
  if (!m) return {}
  const out: Record<string, string> = {}
  for (const line of m[1].split('\n')) {
    const idx = line.indexOf(':')
    if (idx > 0) out[line.slice(0, idx).trim()] = line.slice(idx + 1).trim()
  }
  return out
}

function parseCard(key: string, text: string): CardMeta {
  const fm = frontmatter(text)
  const rawType = fm['类型'] ?? ''
  return {
    key,
    name: (TITLE_RE.exec(text)?.[1] ?? key).trim(),
    type: (rawType.split('·').pop() ?? '概念').trim() || '概念',
    domain: fm['领域'] ?? '',
    oneLine: (ONELINE_RE.exec(text)?.[1] ?? '').trim()
  }
}

export function listCards(): CardMeta[] {
  const dir = notesDir()
  let files: string[]
  try {
    files = readdirSync(dir)
  } catch {
    return []
  }
  return files
    .filter(f => f.endsWith('.md'))
    .sort()
    .map(f => {
      const key = f.slice(0, -3)
      return parseCard(key, readFileSync(join(dir, f), 'utf8'))
    })
}

export function readCard(key: string): CardDetail | null {
  if (!/^[\w\u4e00-\u9fa5. -]+$/.test(key)) return null
  const path = join(notesDir(), `${key}.md`)
  try {
    if (!statSync(path).isFile()) return null
    const markdown = readFileSync(path, 'utf8')
    return { ...parseCard(key, markdown), markdown }
  } catch {
    return null
  }
}
