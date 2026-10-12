import { resolve } from 'node:path'
import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  // 主进程：Node 全权（读 data/、调 Python CLI、开窗口）
  main: {
    plugins: [externalizeDepsPlugin()],
    resolve: {
      alias: { '@main': resolve('src/main'), '@shared': resolve('src/shared') }
    },
    build: {
      rollupOptions: { input: { index: resolve('src/main/index.ts') } }
    }
  },
  // 预加载：白名单桥（renderer 只能看到这里显式暴露的 API）
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: {
      rollupOptions: { input: { index: resolve('src/preload/index.ts') } }
    }
  },
  // 渲染进程：Vue3（业务只在 Python，这里只做展示）
  renderer: {
    resolve: {
      alias: { '@': resolve('src/renderer/src') }
    },
    plugins: [vue()]
  }
})
