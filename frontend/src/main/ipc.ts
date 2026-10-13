/** IPC 处理器注册：renderer 的每个请求都落在这里（薄壳的全部入口）。 */
import { ipcMain } from 'electron'

import {
  IPC,
  type DraftPreview,
  type LlmConfigView,
  type SourceEntry,
  type TrustedSourceInput
} from '../shared/ipc'
import { listCards, readCard } from './data'
import {
  commitDraft,
  draftTopic,
  entryAdd,
  entryRemove,
  historyClear,
  historyList,
  llmConfig,
  llmConfigSave,
  llmProbe,
  loadGraph,
  mechCardsList,
  moduleDelete,
  moduleSave,
  modulesList,
  platformAdd,
  platformRemove,
  platformsList,
  runCli,
  searchTopic
} from './cli'
import { repoRoot } from './paths'

export function registerIpc(): void {
  ipcMain.handle(IPC.repoRoot, () => repoRoot())
  ipcMain.handle(IPC.graphLoad, () => loadGraph())
  ipcMain.handle(IPC.cardsList, () => listCards())
  ipcMain.handle(IPC.cardRead, (_event, key: string) => readCard(key))
  ipcMain.handle(IPC.mechCardsList, () => mechCardsList())
  ipcMain.handle(IPC.cliRun, (_event, args: string[]) => runCli(args))
  ipcMain.handle(IPC.searchTopic, (_event, topic: string, limit?: number) =>
    searchTopic(topic, limit)
  )
  ipcMain.handle(IPC.draftTopic, (_event, topic: string) => draftTopic(topic))
  ipcMain.handle(IPC.commitDraft, (_event, draft: DraftPreview) => commitDraft(draft))
  ipcMain.handle(IPC.historyList, () => historyList())
  ipcMain.handle(IPC.historyClear, () => historyClear())
  ipcMain.handle(IPC.modulesList, () => modulesList())
  ipcMain.handle(IPC.moduleSave, (_event, topic: string, keywords?: string[]) =>
    moduleSave(topic, keywords)
  )
  ipcMain.handle(IPC.moduleDelete, (_event, id: string) => moduleDelete(id))
  ipcMain.handle(IPC.platformsList, () => platformsList())
  ipcMain.handle(IPC.platformAdd, (_event, item: TrustedSourceInput) => platformAdd(item))
  ipcMain.handle(IPC.platformRemove, (_event, id: string) => platformRemove(id))
  ipcMain.handle(IPC.entryAdd, (_event, moduleId: string, entry: SourceEntry) =>
    entryAdd(moduleId, entry)
  )
  ipcMain.handle(IPC.entryRemove, (_event, moduleId: string, title: string) =>
    entryRemove(moduleId, title)
  )
  ipcMain.handle(IPC.llmConfig, () => llmConfig())
  ipcMain.handle(IPC.llmConfigSave, (_event, cfg: LlmConfigView) => llmConfigSave(cfg))
  ipcMain.handle(IPC.llmProbe, (_event, tier?: string) => llmProbe(tier))
}
