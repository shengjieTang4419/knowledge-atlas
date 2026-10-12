import { defineStore } from 'pinia'
import { ref } from 'vue'

import type { GraphData } from '../../../shared/ipc'
import { api } from '@/api'

export const useAtlasStore = defineStore('atlas', () => {
  const repoRoot = ref('')
  const graph = ref<GraphData | null>(null)
  const loading = ref(false)
  const error = ref('')

  async function loadAll(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      repoRoot.value = await api.repoRoot()
      graph.value = await api.graphLoad()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  return { repoRoot, graph, loading, error, loadAll }
})
