/**
 * IPC 契约：main ↔ renderer 的唯一通道定义（契约先行）。
 *
 * 设计原则（薄壳）：
 * - renderer 拿不到 Node，只能通过这里声明的通道要数据；
 * - 所有知识数据由 main 从 `data/` 读或调 Python CLI 取得，renderer 不做业务计算。
 */

export const IPC = {
  repoRoot: 'atlas:repo-root',
  graphLoad: 'atlas:graph-load',
  cardsList: 'atlas:cards-list',
  cardRead: 'atlas:card-read',
  mechCardsList: 'atlas:mech-cards-list',
  cliRun: 'atlas:cli-run',
  searchTopic: 'atlas:search-topic',
  modulesList: 'atlas:modules-list',
  moduleSave: 'atlas:module-save',
  moduleDelete: 'atlas:module-delete',
  sourceAdd: 'atlas:source-add',
  sourceRemove: 'atlas:source-remove'
} as const

/** 关系类型：递进 = is-a/contains（实体↔实体）；应用 = applies-to（机制卡↔实体） */
export type RelationType = '递进' | '应用'

export interface GraphNode {
  key: string
  name: string
  etype: string
  oneLine: string
  domain: string
  color: string
  x: number
  y: number
  w: number
  h: number
}

export interface GraphBox {
  domain: string
  x: number
  y: number
  w: number
  h: number
  color: string
}

export interface GraphLink {
  src: string
  dst: string
  type: RelationType
  reason: string
}

export interface GraphData {
  nodes: GraphNode[]
  boxes: GraphBox[]
  links: GraphLink[]
  dangling: string[]
  width: number
  height: number
}

export interface CardMeta {
  key: string
  name: string
  type: string
  domain: string
  oneLine: string
}

export interface CardDetail extends CardMeta {
  markdown: string
}

/** 机制卡（L4 一等公民，对应 Python `MechanismCard`） */
export interface MechCard {
  name: string
  problem: string
  mechanism: string
  tradeoff: string
  boundary: string
  cases: string[]
}

export interface CliResult {
  ok: boolean
  code: number
  command: string
  stdout: string
  stderr: string
}

/** 可信来源类型（与 Python `app/settings.py` 的 VALID_TYPES 一致，改一处要同步） */
export const SOURCE_TYPES = ['规范', '源码', '书籍', '论文', '博客', '社区'] as const
export type SourceType = (typeof SOURCE_TYPES)[number]

/** 可信源条目（设置页维护） */
export interface SourceItem {
  name: string
  type: string
  why: string
  locator: string
}

/** 搜索命中的来源：多一个 origin 说明它从哪来 */
export interface SourceHit extends SourceItem {
  origin: 'builtin' | 'user' | 'llm'
}

/** 模块来路：AI 搜主题时自动收录 / 在设置页手工建 */
export type ModuleOrigin = 'auto' | 'manual'

/** 可信源「搜索模块」= 某 topic 的可信源集合（对应 Python `settings.TrustedModule`） */
export interface TrustedModule {
  id: string
  topic: string
  origin: ModuleOrigin
  keywords: string[]
  createdAt: string
  updatedAt: string
  sources: SourceItem[]
}

/** 搜主题结果（对应 Python `retrieve.search_topic()`） */
export interface SearchResult {
  topic: string
  keywords: string[]
  sources: SourceHit[]
  /** 是否找到可信源 */
  matched: boolean
  /** 是否该提示去配置（= 没找到） */
  needsConfig: boolean
  /** 本次是否**新收录**了模块（界面提示「已收录到设置」） */
  autoCollected: boolean
  /** 命中的模块 id；未命中为空串 */
  moduleId: string
  /** 已有模块总数：区分「没配过」与「配了但不匹配」两种提示口径 */
  moduleCount: number
  /** 是否具备 AI 判定条件（无 LLM key 时界面解释「为什么没自动生成」） */
  llmAvailable: boolean
}

/** preload 通过 contextBridge 暴露给 renderer 的 API（window.api） */
export interface AtlasApi {
  repoRoot(): Promise<string>
  graphLoad(): Promise<GraphData>
  cardsList(): Promise<CardMeta[]>
  cardRead(key: string): Promise<CardDetail | null>
  mechCardsList(): Promise<MechCard[]>
  cliRun(args: string[]): Promise<CliResult>
  searchTopic(topic: string, limit?: number): Promise<SearchResult>
  modulesList(): Promise<TrustedModule[]>
  moduleSave(topic: string, keywords?: string[]): Promise<TrustedModule[]>
  moduleDelete(id: string): Promise<TrustedModule[]>
  sourceAdd(moduleId: string, item: SourceItem): Promise<TrustedModule[]>
  sourceRemove(moduleId: string, name: string): Promise<TrustedModule[]>
}
