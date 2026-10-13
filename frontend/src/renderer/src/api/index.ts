/**
 * api：window.api 的类型化封装。
 *
 * 组件不直接碰 window，一律走这里——将来换外壳（Tauri/web）只改这一个文件。
 */
import type {
  AtlasApi,
  CardDetail,
  CardMeta,
  CliResult,
  CommitResult,
  DraftPreview,
  GraphData,
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
} from '../../../shared/ipc'

function bridge(): AtlasApi {
  if (typeof window === 'undefined' || !window.api) {
    throw new Error('IPC 桥不可用：请在 Electron 中运行（make app）')
  }
  return window.api
}

/**
 * IPC 载荷必须是**裸数据**：Vue 的响应式对象是 Proxy，跨 IPC 会抛
 * 「An object could not be cloned.」（实测 `structuredClone(reactive(x))` → DataCloneError）。
 * 带载荷的调用在桥这一层脱一次代理——载荷本来就要 JSON 序列化给 CLI，代价为零。
 */
function payload<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export const api = {
  repoRoot: (): Promise<string> => bridge().repoRoot(),
  graphLoad: (): Promise<GraphData> => bridge().graphLoad(),
  cardsList: (): Promise<CardMeta[]> => bridge().cardsList(),
  cardRead: (key: string): Promise<CardDetail | null> => bridge().cardRead(key),
  mechCardsList: (): Promise<MechCard[]> => bridge().mechCardsList(),
  cliRun: (args: string[]): Promise<CliResult> => bridge().cliRun(args),
  searchTopic: (topic: string, limit?: number): Promise<SearchResult> =>
    bridge().searchTopic(topic, limit),
  draftTopic: (topic: string): Promise<DraftPreview> => bridge().draftTopic(topic),
  commitDraft: (draft: DraftPreview): Promise<CommitResult> => bridge().commitDraft(draft),
  historyList: (): Promise<HistoryItem[]> => bridge().historyList(),
  historyClear: (): Promise<HistoryItem[]> => bridge().historyClear(),
  modulesList: (): Promise<TrustedModule[]> => bridge().modulesList(),
  moduleSave: (topic: string, keywords?: string[]): Promise<TrustedModule[]> =>
    bridge().moduleSave(topic, keywords),
  moduleDelete: (id: string): Promise<TrustedModule[]> => bridge().moduleDelete(id),
  platformsList: (): Promise<TrustedSource[]> => bridge().platformsList(),
  platformAdd: (item: TrustedSourceInput): Promise<PlatformAddResult> => bridge().platformAdd(item),
  platformRemove: (id: string): Promise<TrustedSource[]> => bridge().platformRemove(id),
  entryAdd: (moduleId: string, entry: SourceEntry): Promise<TrustedModule[]> =>
    bridge().entryAdd(moduleId, entry),
  entryRemove: (moduleId: string, title: string): Promise<TrustedModule[]> =>
    bridge().entryRemove(moduleId, title),
  llmConfig: (): Promise<LlmConfigView> => bridge().llmConfig(),
  llmConfigSave: (cfg: LlmConfigView): Promise<LlmConfigView> =>
    bridge().llmConfigSave(payload(cfg)),
  llmProbe: (tier?: string): Promise<LlmProbeResult[]> => bridge().llmProbe(tier)
}
