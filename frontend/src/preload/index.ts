/**
 * 预加载：把 IPC 包成白名单 API 暴露给 renderer（renderer 拿不到 Node）。
 *
 * 只暴露本项目声明的 5 个方法，不透出 ipcRenderer 本体——
 * 比通用 preload 工具包更小的攻击面，也不需要额外依赖。
 * 恒开 contextIsolation（见 main/index.ts 的 webPreferences）。
 */
import { contextBridge, ipcRenderer } from 'electron'

import { IPC, type AtlasApi, type SourceItem } from '../shared/ipc'

const api: AtlasApi = {
  repoRoot: () => ipcRenderer.invoke(IPC.repoRoot),
  graphLoad: () => ipcRenderer.invoke(IPC.graphLoad),
  cardsList: () => ipcRenderer.invoke(IPC.cardsList),
  cardRead: key => ipcRenderer.invoke(IPC.cardRead, key),
  mechCardsList: () => ipcRenderer.invoke(IPC.mechCardsList),
  cliRun: args => ipcRenderer.invoke(IPC.cliRun, args),
  searchTopic: (topic: string, limit?: number) => ipcRenderer.invoke(IPC.searchTopic, topic, limit),
  modulesList: () => ipcRenderer.invoke(IPC.modulesList),
  moduleSave: (topic: string, keywords?: string[]) =>
    ipcRenderer.invoke(IPC.moduleSave, topic, keywords),
  moduleDelete: (id: string) => ipcRenderer.invoke(IPC.moduleDelete, id),
  sourceAdd: (moduleId: string, item: SourceItem) =>
    ipcRenderer.invoke(IPC.sourceAdd, moduleId, item),
  sourceRemove: (moduleId: string, name: string) =>
    ipcRenderer.invoke(IPC.sourceRemove, moduleId, name)
}

contextBridge.exposeInMainWorld('api', api)
