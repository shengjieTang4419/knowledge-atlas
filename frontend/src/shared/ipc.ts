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
  draftTopic: 'atlas:draft-topic',
  commitDraft: 'atlas:commit-draft',
  historyList: 'atlas:history-list',
  historyClear: 'atlas:history-clear',
  modulesList: 'atlas:modules-list',
  moduleSave: 'atlas:module-save',
  moduleDelete: 'atlas:module-delete',
  platformsList: 'atlas:platforms-list',
  platformAdd: 'atlas:platform-add',
  platformRemove: 'atlas:platform-remove',
  entryAdd: 'atlas:entry-add',
  entryRemove: 'atlas:entry-remove',
  llmConfig: 'atlas:llm-config',
  llmConfigSave: 'atlas:llm-config-save',
  llmProbe: 'atlas:llm-probe'
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

/** 可信源来路：内置 curated / AI 判定自动收录 / 手工配置 */
export type SourceOrigin = 'builtin' | 'auto' | 'manual'

/**
 * 可信源 = **平台级**（GitHub / arXiv / Oracle 官方文档 这种泛化出处），跨主题复用、全局一份。
 * 平台上的具体文件是 `SourceEntry`（条目）——两者混成一层就会攒出一堆一次性的「可信源」。
 */
export interface TrustedSource {
  /** 归一 id：宿主域名优先（github.com）——同一个站只算一个平台 */
  id: string
  name: string
  type: string
  /** 这个平台为什么可信（跨主题成立） */
  why: string
  /** 平台入口 */
  home: string
  origin: SourceOrigin
}

/** 新建可信源时前端填的字段（id 由主进程/Python 归一，前端不算） */
export interface TrustedSourceInput {
  name: string
  type: string
  why: string
  home: string
}

/** 保存可信源的回报：`platform` 是**归一后**入库的那条（同站会归入已有平台，名字可能不是你填的） */
export interface PlatformAddResult {
  platform: TrustedSource
  platforms: TrustedSource[]
}

/** 条目 = 某平台上具体哪个文件/页面，挂在主题模块下 */
export interface SourceEntry {
  title: string
  /** 所属平台 id（TrustedSource.id） */
  source: string
  locator: string
  /** 这条为什么值得读 */
  note: string
}

/** 模块来路：AI 搜主题时自动收录 / 在设置页手工建 */
export type ModuleOrigin = 'auto' | 'manual'

/** 主题模块 = 某 topic 的**条目**集合（对应 Python `settings.TrustedModule`） */
export interface TrustedModule {
  id: string
  topic: string
  origin: ModuleOrigin
  keywords: string[]
  createdAt: string
  updatedAt: string
  items: SourceEntry[]
}

/** 搜主题结果（对应 Python `retrieve.search_topic()`） */
export interface SearchResult {
  topic: string
  keywords: string[]
  /** 可信源（平台级，≤5）：收敛后的「找到了什么」 */
  sources: TrustedSource[]
  /** 条目（文件级）：这个主题具体该读哪些 */
  items: SourceEntry[]
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

/** 一条搜索历史（对应 Python `settings.HistoryItem`；持久化，侧栏展示） */
export interface HistoryItem {
  topic: string
  /** ISO 时间（Asia/Shanghai） */
  at: string
  matched: boolean
  /** 命中平台数 */
  sourceCount: number
}

/** 预演里的一个实体（对应 Python `Entity`） */
export interface DraftEntity {
  name: string
  type: string
  oneLine: string
}

/** 预演里的一条边（对应 Python `Edge`） */
export interface DraftEdge {
  src: string
  dst: string
  type: RelationType
  confidence: string
  reason: string
}

/** 端到端预演结果（`app.cli draft` 的 JSON，人工审核后回传给 `commit`） */
export interface DraftPreview {
  topic: string
  keywords: string[]
  sources: TrustedSource[]
  items: SourceEntry[]
  matched: boolean
  needsConfig: boolean
  /** 抽不出实体时用来区分「模型调用失败」与「模型没给」：非空即整条降级链的失败摘要 */
  llmError: string
  /** 本次实际服务的资源（如 `ifans/gpt-plus`）；没成功则为空 */
  llmRoute: string
  /** 链首没服务成、由后面某个接住 = 降级（降级必须可见） */
  llmDegraded: boolean
  entities: DraftEntity[]
  relations: { src: string; dst: string; type: RelationType }[]
  cards: MechCard[]
  edges: DraftEdge[]
}

/** 写盘结果（`app.cli commit` 的 JSON） */
export interface CommitResult {
  writtenEntities: string[]
  cards: number
  edges: number
}

/** 链路模式：fallback = 逐个试到成功；moa = 多模型都跑一遍再融合 */
export type ChainMode = 'fallback' | 'moa'

/** 一家模型资源（对应 Python `settings.LlmProvider`） */
export interface LlmProviderConfig {
  id: string
  baseUrl: string
  /** **明文 Key 不回传**：读到的恒为空串，提交时留空 = 不改（要换就重填） */
  apiKey: string
  /** 引用环境变量名（密钥不落盘，推荐） */
  apiKeyEnv: string
  hasKey: boolean
  keyHint: string
}

/** 一个档位的链路；`entries` 写法为 `<model>` 或 `<provider>/<model>` */
export interface LlmChainConfig {
  mode: ChainMode
  entries: string[]
}

/** 模型资源配置视图（`app.cli llm-config`），存于 `data/settings/llm.json`（不入 git） */
export interface LlmConfigView {
  /** env = 按 `.env` 播种（还没在界面存过）；file = 界面存过，以文件为准 */
  source: 'env' | 'file'
  path: string
  defaultProvider: string
  maxAttempts: number
  timeout: number
  providers: LlmProviderConfig[]
  chains: Record<string, LlmChainConfig>
}

/** 单个候选的真调结论（`app.cli llm-probe`） */
export interface LlmProbeItem {
  provider: string
  model: string
  ok: boolean
  ms: number
  error: string
}

export interface LlmProbeResult {
  tier: string
  results: LlmProbeItem[]
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
  draftTopic(topic: string): Promise<DraftPreview>
  commitDraft(draft: DraftPreview): Promise<CommitResult>
  historyList(): Promise<HistoryItem[]>
  historyClear(): Promise<HistoryItem[]>
  modulesList(): Promise<TrustedModule[]>
  moduleSave(topic: string, keywords?: string[]): Promise<TrustedModule[]>
  moduleDelete(id: string): Promise<TrustedModule[]>
  platformsList(): Promise<TrustedSource[]>
  platformAdd(item: TrustedSourceInput): Promise<PlatformAddResult>
  platformRemove(id: string): Promise<TrustedSource[]>
  entryAdd(moduleId: string, entry: SourceEntry): Promise<TrustedModule[]>
  entryRemove(moduleId: string, title: string): Promise<TrustedModule[]>
  llmConfig(): Promise<LlmConfigView>
  llmConfigSave(cfg: LlmConfigView): Promise<LlmConfigView>
  llmProbe(tier?: string): Promise<LlmProbeResult[]>
}
