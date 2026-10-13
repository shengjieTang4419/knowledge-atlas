import { defineStore } from 'pinia'
import { ref } from 'vue'

import type { GraphData, HistoryItem } from '../../../shared/ipc'
import { api } from '@/api'

export type SettingsTab = 'model' | 'sources' | 'about'

export const useAtlasStore = defineStore('atlas', () => {
  const repoRoot = ref('')
  const graph = ref<GraphData | null>(null)
  const loading = ref(false)
  const error = ref('')

  // 搜索历史：落盘在 data/settings/settings.json，侧栏「搜索」下方与搜索页共用这一份
  const history = ref<HistoryItem[]>([])

  async function loadHistory(): Promise<void> {
    history.value = await api.historyList()
  }

  async function clearHistory(): Promise<void> {
    history.value = await api.historyClear()
  }

  // 系统配置弹层：全局态（右下单齿轮开它），不走路由——
  // 否则「从审核页跳去配置」会丢掉当前草稿，回来还得重跑一遍模型
  const settingsOpen = ref(false)
  const settingsTab = ref<SettingsTab>('model')

  function openSettings(tab: SettingsTab = 'model'): void {
    settingsTab.value = tab
    settingsOpen.value = true
  }

  function closeSettings(): void {
    settingsOpen.value = false
  }

  async function loadAll(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      repoRoot.value = await api.repoRoot()
      graph.value = await api.graphLoad()
      // 历史读不到不静默吞：它与图谱同走 Python CLI，坏了就该看见
      await loadHistory()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  return {
    repoRoot,
    graph,
    loading,
    error,
    history,
    loadHistory,
    clearHistory,
    settingsOpen,
    settingsTab,
    openSettings,
    closeSettings,
    loadAll
  }
})
