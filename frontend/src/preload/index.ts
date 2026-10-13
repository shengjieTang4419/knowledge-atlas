/**
 * 预加载：把 IPC 包成白名单 API 暴露给 renderer（renderer 拿不到 Node）。
 *
 * 只暴露本项目声明的通道，不透出 ipcRenderer 本体——
 * 比通用 preload 工具包更小的攻击面，也不需要额外依赖。
 * 恒开 contextIsolation（见 main/index.ts 的 webPreferences）。
 */
import { contextBridge, ipcRenderer } from 'electron'

import {
  IPC,
  type AtlasApi,
  type DraftPreview,
  type LlmConfigView,
  type SourceEntry,
  type TrustedSourceInput
} from '../shared/ipc'

const api: AtlasApi = {
  repoRoot: () => ipcRenderer.invoke(IPC.repoRoot),
  graphLoad: () => ipcRenderer.invoke(IPC.graphLoad),
  cardsList: () => ipcRenderer.invoke(IPC.cardsList),
  cardRead: key => ipcRenderer.invoke(IPC.cardRead, key),
  mechCardsList: () => ipcRenderer.invoke(IPC.mechCardsList),
  cliRun: args => ipcRenderer.invoke(IPC.cliRun, args),
  searchTopic: (topic: string, limit?: number) => ipcRenderer.invoke(IPC.searchTopic, topic, limit),
  draftTopic: (topic: string) => ipcRenderer.invoke(IPC.draftTopic, topic),
  commitDraft: (draft: DraftPreview) => ipcRenderer.invoke(IPC.commitDraft, draft),
  historyList: () => ipcRenderer.invoke(IPC.historyList),
  historyClear: () => ipcRenderer.invoke(IPC.historyClear),
  modulesList: () => ipcRenderer.invoke(IPC.modulesList),
  moduleSave: (topic: string, keywords?: string[]) =>
    ipcRenderer.invoke(IPC.moduleSave, topic, keywords),
  moduleDelete: (id: string) => ipcRenderer.invoke(IPC.moduleDelete, id),
  platformsList: () => ipcRenderer.invoke(IPC.platformsList),
  platformAdd: (item: TrustedSourceInput) => ipcRenderer.invoke(IPC.platformAdd, item),
  platformRemove: (id: string) => ipcRenderer.invoke(IPC.platformRemove, id),
  entryAdd: (moduleId: string, entry: SourceEntry) =>
    ipcRenderer.invoke(IPC.entryAdd, moduleId, entry),
  entryRemove: (moduleId: string, title: string) =>
    ipcRenderer.invoke(IPC.entryRemove, moduleId, title),
  llmConfig: () => ipcRenderer.invoke(IPC.llmConfig),
  llmConfigSave: (cfg: LlmConfigView) => ipcRenderer.invoke(IPC.llmConfigSave, cfg),
  llmProbe: (tier?: string) => ipcRenderer.invoke(IPC.llmProbe, tier)
}

contextBridge.exposeInMainWorld('api', api)
