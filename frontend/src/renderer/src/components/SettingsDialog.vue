<script setup lang="ts">
/**
 * 系统配置弹层（右下齿轮打开）：左侧分类 + 右侧面板。
 *
 * 为什么是弹层不是路由页：配置是**随时要开**的东西（换模型、配源），做成路由会打断手上的活——
 * 从审核页跳过去就丢了草稿，回来得重跑一遍模型。弹层不打断当前页。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

import ModelSettings from '@/components/ModelSettings.vue'
import SourceSettings from '@/components/SourceSettings.vue'
import { api } from '@/api'
import { useAtlasStore, type SettingsTab } from '@/stores/atlas'

const store = useAtlasStore()

const tabs: { id: SettingsTab; label: string; hint: string }[] = [
  { id: 'model', label: '模型', hint: 'Provider · 降级链 · MoA' },
  { id: 'sources', label: '可信源', hint: '平台 + 主题模块' },
  { id: 'about', label: '关于', hint: '仓库与数据位置' }
]

/** 「关于」页要显示的真实路径（面板打开时才取，别在启动时多打一次 IPC） */
const about = ref<{ root: string; configPath: string } | null>(null)

async function loadAbout(): Promise<void> {
  if (about.value) return
  try {
    const [root, cfg] = await Promise.all([api.repoRoot(), api.llmConfig()])
    about.value = { root, configPath: cfg.path }
  } catch (e) {
    about.value = { root: e instanceof Error ? e.message : String(e), configPath: '—' }
  }
}

async function pick(tab: SettingsTab): Promise<void> {
  store.settingsTab = tab
  if (tab === 'about') await loadAbout()
}

function onKey(e: KeyboardEvent): void {
  if (e.key === 'Escape' && store.settingsOpen) store.closeSettings()
}

onMounted(() => {
  window.addEventListener('keydown', onKey)
  if (store.settingsTab === 'about') void loadAbout()
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <div v-if="store.settingsOpen" class="backdrop" @click.self="store.closeSettings()">
      <div class="dialog" role="dialog" aria-label="系统配置">
        <aside class="rail">
          <div class="title">配置</div>
          <button
            v-for="t in tabs"
            :key="t.id"
            :class="{ on: store.settingsTab === t.id }"
            @click="pick(t.id)"
          >
            <span class="label">{{ t.label }}</span>
            <span class="hint mono">{{ t.hint }}</span>
          </button>
        </aside>

        <section class="panel">
          <header class="panel-head">
            <h2>{{ tabs.find(t => t.id === store.settingsTab)?.label }}</h2>
            <button class="close" title="关闭（Esc）" @click="store.closeSettings()">✕</button>
          </header>

          <div class="panel-body">
            <ModelSettings v-if="store.settingsTab === 'model'" />
            <SourceSettings v-else-if="store.settingsTab === 'sources'" />
            <div v-else class="about">
              <p class="dim">知识图谱数据与用户配置都在仓库内，凭据只落本机。</p>
              <dl>
                <dt>仓库根</dt>
                <dd class="mono">{{ about?.root ?? '读取中…' }}</dd>
                <dt>模型配置</dt>
                <dd class="mono">{{ about?.configPath ?? '读取中…' }}</dd>
                <dt>可信源模块</dt>
                <dd class="mono">data/settings/settings.json</dd>
                <dt>真相源（入 git）</dt>
                <dd class="mono">data/wiki/ · data/graph/edges.md · data/mechanism/cards.md</dd>
              </dl>
            </div>
          </div>
        </section>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(6, 9, 13, 0.62);
  backdrop-filter: blur(2px);
}

.dialog {
  display: flex;
  width: min(940px, calc(100vw - 48px));
  height: min(660px, calc(100vh - 64px));
  overflow: hidden;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 14px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.5);
}

.rail {
  display: flex;
  flex-direction: column;
  gap: 3px;
  width: 186px;
  padding: 16px 12px;
  background: #0d131b;
  border-right: 1px solid var(--line);
}

.rail .title {
  padding: 0 9px 10px;
  font-family: 'Songti SC', 'Noto Serif SC', serif;
  font-size: 15px;
}

.rail button {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  text-align: left;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
}

.rail button:hover {
  border-color: var(--line);
}

.rail button.on {
  background: rgba(79, 209, 197, 0.08);
  border-color: rgba(79, 209, 197, 0.4);
}

.rail .label {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--ink);
}

.rail .hint {
  font-size: 10px;
  color: var(--dim);
}

.panel {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--line);
}

.panel-head h2 {
  font-size: 15px;
}

.close {
  padding: 2px 8px;
  font-size: 13px;
  color: var(--dim);
}

.close:hover {
  color: var(--ink);
}

.panel-body {
  flex: 1;
  padding: 16px 18px 22px;
  overflow: auto;
}

.about .dim {
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--dim);
}

dl {
  margin-top: 14px;
}

dt {
  margin-top: 12px;
  font-size: 11.5px;
  color: var(--dim);
}

dd {
  margin-top: 3px;
  font-size: 12px;
  color: var(--ink);
  word-break: break-all;
}
</style>
