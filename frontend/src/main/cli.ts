/**
 * Python 业务层调用：把仓库根的 CLI 当子进程跑。
 *
 * 为什么不用 TS 重写：五层逻辑（分块/向量/召回/判边/画像）的唯一真相源是 Python，
 * 壳只负责转发。这样换 Electron 之外的外壳（Tauri / web）时业务零重写。
 *
 * 契约边界：CLI 吐的是 Python 侧字段名（snake_case），这里映射成前端模型（camelCase）。
 */
import { execFile } from 'node:child_process'
import { rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { promisify } from 'node:util'

import type {
  CliResult,
  CommitResult,
  DraftPreview,
  GraphBox,
  GraphData,
  GraphLink,
  GraphNode,
  HistoryItem,
  LlmConfigView,
  LlmProbeResult,
  MechCard,
  PlatformAddResult,
  SearchResult,
  SourceEntry,
  TrustedModule,
  TrustedSource,
  TrustedSourceInput
} from '../shared/ipc'
import { repoRoot } from './paths'

const run = promisify(execFile)

/** Python `app.cli view --json` 的原始输出（字段名以 Python 为准，勿改这里去凑前端） */
interface RawNode {
  key: string
  name: string
  etype: string
  one_line: string
  domain: string
  color: string
  x: number
  y: number
  w: number
  h: number
}

interface RawGraph {
  nodes: RawNode[]
  boxes: GraphBox[]
  links: GraphLink[]
  dangling: string[]
  width: number
  height: number
}

/** 优先 uv（项目依赖在 .venv），退化为系统 python3 + PYTHONPATH */
async function runner(): Promise<{ cmd: string; args: string[] }> {
  try {
    await run('uv', ['--version'], { timeout: 5000 })
    return { cmd: 'uv', args: ['run', 'python', '-m', 'app.cli'] }
  } catch {
    return { cmd: 'python3', args: ['-m', 'app.cli'] }
  }
}

export async function runCli(args: string[], timeoutMs = 60_000): Promise<CliResult> {
  const { cmd, args: base } = await runner()
  const command = [cmd, ...base, ...args].join(' ')
  try {
    const { stdout, stderr } = await run(cmd, [...base, ...args], {
      cwd: repoRoot(),
      timeout: timeoutMs,
      maxBuffer: 8 * 1024 * 1024,
      env: { ...process.env, PYTHONPATH: repoRoot() }
    })
    return { ok: true, code: 0, command, stdout, stderr }
  } catch (err) {
    const e = err as { code?: number; stdout?: string; stderr?: string; message?: string }
    return {
      ok: false,
      code: typeof e.code === 'number' ? e.code : 1,
      command,
      stdout: e.stdout ?? '',
      stderr: e.stderr || e.message || '调用失败'
    }
  }
}

function toGraphNode(raw: RawNode): GraphNode {
  return {
    key: raw.key,
    name: raw.name,
    etype: raw.etype,
    oneLine: raw.one_line,
    domain: raw.domain,
    color: raw.color,
    x: raw.x,
    y: raw.y,
    w: raw.w,
    h: raw.h
  }
}

/** 图谱数据来自 Python 视图层（`app.cli view --json`），保证布局逻辑单一真相源 */
export async function loadGraph(): Promise<GraphData> {
  const res = await runCli(['view', '--json'])
  if (!res.ok) throw new Error(res.stderr || '图谱加载失败')
  const raw = JSON.parse(res.stdout) as RawGraph
  return {
    nodes: raw.nodes.map(toGraphNode),
    boxes: raw.boxes,
    links: raw.links,
    dangling: raw.dangling,
    width: raw.width,
    height: raw.height
  }
}

// ---------- 搜主题 / 可信源设置（均转发 Python CLI）----------

function parseJson<T>(res: CliResult, what: string): T {
  if (!res.ok) throw new Error(res.stderr.trim() || `${what}失败`)
  try {
    return JSON.parse(res.stdout) as T
  } catch {
    throw new Error(`${what}返回的不是合法 JSON：${res.stdout.slice(0, 200)}`)
  }
}

export async function searchTopic(topic: string, limit = 5): Promise<SearchResult> {
  // 无匹配时 CLI 也退出 0（结果由 JSON 表达），所以这里只需解析
  const res = await runCli(['search', topic, '--json', '--limit', String(limit)])
  return parseJson<SearchResult>(res, '搜索主题')
}

export async function draftTopic(topic: string): Promise<DraftPreview> {
  // draft 恒吐 JSON（无 --json 开关），只算不写盘，供人工审核
  const res = await runCli(['draft', topic])
  return parseJson<DraftPreview>(res, '生成预览')
}

export async function commitDraft(draft: DraftPreview): Promise<CommitResult> {
  // 审核后的 draft 经临时文件回传（比走 argv 更耐大小/转义），Python 侧读文件写盘
  const file = join(
    tmpdir(),
    `atlas-draft-${Date.now()}-${Math.random().toString(36).slice(2)}.json`
  )
  writeFileSync(file, JSON.stringify(draft), 'utf-8')
  try {
    const res = await runCli(['commit', '--file', file])
    return parseJson<CommitResult>(res, '写入图谱')
  } finally {
    rmSync(file, { force: true })
  }
}

export async function modulesList(): Promise<TrustedModule[]> {
  const res = await runCli(['modules', '--json'])
  return parseJson<{ modules: TrustedModule[] }>(res, '读取模块').modules
}

export async function mechCardsList(): Promise<MechCard[]> {
  const res = await runCli(['cards', '--json'])
  return parseJson<MechCard[]>(res, '读取机制卡')
}

export async function historyList(): Promise<HistoryItem[]> {
  const res = await runCli(['history', '--json'])
  return parseJson<{ history: HistoryItem[] }>(res, '读取搜索历史').history
}

export async function historyClear(): Promise<HistoryItem[]> {
  const res = await runCli(['history-clear', '--json'])
  return parseJson<{ history: HistoryItem[] }>(res, '清空搜索历史').history
}

export async function moduleSave(topic: string, keywords: string[] = []): Promise<TrustedModule[]> {
  const args = ['module-save', '--topic', topic, '--json']
  if (keywords.length) args.push('--keywords', keywords.join(','))
  const res = await runCli(args)
  return parseJson<{ modules: TrustedModule[] }>(res, '保存模块').modules
}

export async function moduleDelete(id: string): Promise<TrustedModule[]> {
  const res = await runCli(['module-delete', '--id', id, '--json'])
  return parseJson<{ modules: TrustedModule[] }>(res, '删除模块').modules
}

export async function platformsList(): Promise<TrustedSource[]> {
  const res = await runCli(['platforms', '--json'])
  return parseJson<{ platforms: TrustedSource[] }>(res, '读取可信源').platforms
}

export async function platformAdd(item: TrustedSourceInput): Promise<PlatformAddResult> {
  // id 由 Python 归一（宿主域名优先），前端不猜
  const res = await runCli([
    'platform-add',
    '--name',
    item.name,
    '--type',
    item.type,
    '--home',
    item.home,
    '--why',
    item.why,
    '--json'
  ])
  return parseJson<PlatformAddResult>(res, '保存可信源')
}

export async function platformRemove(id: string): Promise<TrustedSource[]> {
  const res = await runCli(['platform-remove', '--id', id, '--json'])
  return parseJson<{ platforms: TrustedSource[] }>(res, '删除可信源').platforms
}

export async function entryAdd(moduleId: string, entry: SourceEntry): Promise<TrustedModule[]> {
  const res = await runCli([
    'entry-add',
    '--module',
    moduleId,
    '--title',
    entry.title,
    '--source',
    entry.source,
    '--locator',
    entry.locator,
    '--note',
    entry.note,
    '--json'
  ])
  return parseJson<{ modules: TrustedModule[] }>(res, '保存条目').modules
}

export async function entryRemove(moduleId: string, title: string): Promise<TrustedModule[]> {
  const res = await runCli(['entry-remove', '--module', moduleId, '--title', title, '--json'])
  return parseJson<{ modules: TrustedModule[] }>(res, '删除条目').modules
}

// ---------- 模型资源（系统配置弹层里改，落 data/settings/llm.json）----------

export async function llmConfig(): Promise<LlmConfigView> {
  const res = await runCli(['llm-config', '--json'])
  return parseJson<LlmConfigView>(res, '读取模型配置')
}

export async function llmConfigSave(cfg: LlmConfigView): Promise<LlmConfigView> {
  // 与 commit 同法：走临时文件（配置含 Key，比 argv 更稳、也不进进程列表）
  const file = join(tmpdir(), `atlas-llm-${Date.now()}-${Math.random().toString(36).slice(2)}.json`)
  writeFileSync(file, JSON.stringify(cfg), 'utf-8')
  try {
    const res = await runCli(['llm-config-save', '--file', file])
    return parseJson<LlmConfigView>(res, '保存模型配置')
  } finally {
    rmSync(file, { force: true })
  }
}

export async function llmProbe(tier = 'all'): Promise<LlmProbeResult[]> {
  // 真调：最坏耗时 ≈ 单次超时 × 最多尝试数，故给足超时（默认 60s 会被截断）
  const res = await runCli(['llm-probe', '--tier', tier], 300_000)
  return parseJson<{ tiers: LlmProbeResult[] }>(res, '测试模型连通').tiers
}
