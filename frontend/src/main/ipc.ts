/** IPC 处理器注册：renderer 的每个请求都落在这里（薄壳的全部入口）。 */
import { ipcMain } from 'electron'

import { IPC, type SourceItem } from '../shared/ipc'
import { listCards, readCard } from './data'
import {
  loadGraph,
  mechCardsList,
  moduleDelete,
  moduleSave,
  modulesList,
  runCli,
  searchTopic,
  sourceAdd,
  sourceRemove
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
  ipcMain.handle(IPC.modulesList, () => modulesList())
  ipcMain.handle(IPC.moduleSave, (_event, topic: string, keywords?: string[]) =>
    moduleSave(topic, keywords)
  )
  ipcMain.handle(IPC.moduleDelete, (_event, id: string) => moduleDelete(id))
  ipcMain.handle(IPC.sourceAdd, (_event, moduleId: string, item: SourceItem) =>
    sourceAdd(moduleId, item)
  )
  ipcMain.handle(IPC.sourceRemove, (_event, moduleId: string, name: string) =>
    sourceRemove(moduleId, name)
  )
}
