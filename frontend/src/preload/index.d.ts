import type { AtlasApi } from '../shared/ipc'

declare global {
  interface Window {
    api: AtlasApi
  }
}

export {}
