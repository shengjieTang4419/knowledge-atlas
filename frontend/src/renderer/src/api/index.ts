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
  GraphData,
  MechCard,
  SearchResult,
  SourceItem,
  TrustedModule
} from '../../../shared/ipc'

function bridge(): AtlasApi {
  if (typeof window === 'undefined' || !window.api) {
    throw new Error('IPC 桥不可用：请在 Electron 中运行（make app）')
  }
  return window.api
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
  modulesList: (): Promise<TrustedModule[]> => bridge().modulesList(),
  moduleSave: (topic: string, keywords?: string[]): Promise<TrustedModule[]> =>
    bridge().moduleSave(topic, keywords),
  moduleDelete: (id: string): Promise<TrustedModule[]> => bridge().moduleDelete(id),
  sourceAdd: (moduleId: string, item: SourceItem): Promise<TrustedModule[]> =>
    bridge().sourceAdd(moduleId, item),
  sourceRemove: (moduleId: string, name: string): Promise<TrustedModule[]> =>
    bridge().sourceRemove(moduleId, name)
}
