<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'

import SettingsDialog from '@/components/SettingsDialog.vue'
import { useAtlasStore } from '@/stores/atlas'

const store = useAtlasStore()
const router = useRouter()
onMounted(() => void store.loadAll())

/** 菜单按设计文档的分层组织（L1·L2 输入 / L3 结构 / L4 迁移）；配置走右下齿轮弹层 */
const nav = [
  { to: '/search', label: '搜索', hint: 'L1·L2 · 主题 → 可信源' },
  { to: '/graph', label: '图谱层', hint: 'L3 · 实体与关系' },
  { to: '/cards', label: '实体卡', hint: 'L3 · 血肉文档（markdown）' },
  { to: '/mechanism', label: '知识层', hint: 'L4 · 机制卡（金线）' },
  { to: '/cli', label: '跑层', hint: 'CLI · 逐层调试' }
]
// 历史挂在「搜索」正下方，故跳过第一项再渲染其余菜单
const restNav = nav.slice(1)

/** 点历史 = 回搜这个主题：走 query，搜索页看到就自动重跑 */
function openHistory(topic: string): void {
  void router.push({ path: '/search', query: { topic } })
}

function historyHint(topic: string, matched: boolean, count: number, at: string): string {
  const result = matched ? `命中 ${count} 个可信源` : '未命中可信源'
  return `${topic}\n${result} · ${at.replace('T', ' ').slice(0, 16)}`
}
</script>

<template>
  <div class="shell">
    <aside class="side">
      <div class="brand">
        <h1>Knowledge Atlas</h1>
        <p class="mono path">{{ store.repoRoot || '未定位仓库根' }}</p>
      </div>

      <nav>
        <RouterLink :to="nav[0].to" class="item">
          <span class="label">{{ nav[0].label }}</span>
          <span class="hint mono">{{ nav[0].hint }}</span>
        </RouterLink>

        <!-- 搜索历史：持久化在 data/settings/settings.json，重启还在 -->
        <div class="hist">
          <div class="hist-head">
            <span class="hist-title">历史</span>
            <button
              v-if="store.history.length"
              class="hist-clear"
              title="清空搜索历史"
              @click="store.clearHistory()"
            >
              清空
            </button>
          </div>
          <ul v-if="store.history.length" class="hist-list">
            <li v-for="h in store.history" :key="h.topic">
              <button
                class="hist-item"
                :title="historyHint(h.topic, h.matched, h.sourceCount, h.at)"
                @click="openHistory(h.topic)"
              >
                <span class="hist-dot" :class="h.matched ? 'on' : 'off'" />
                <span class="hist-topic">{{ h.topic }}</span>
              </button>
            </li>
          </ul>
          <p v-else class="hist-empty">搜过的主题会留在这里</p>
        </div>

        <RouterLink v-for="n in restNav" :key="n.to" :to="n.to" class="item">
          <span class="label">{{ n.label }}</span>
          <span class="hint mono">{{ n.hint }}</span>
        </RouterLink>
      </nav>

      <div class="foot mono">
        <div>实体 {{ store.graph?.nodes.length ?? '—' }}</div>
        <div>边 {{ store.graph?.links.length ?? '—' }}</div>
        <div v-if="store.graph?.dangling.length" class="warn">
          未建卡边 {{ store.graph.dangling.length }}
        </div>
      </div>
    </aside>

    <main class="body">
      <div v-if="store.error" class="err mono">{{ store.error }}</div>
      <div v-else-if="store.loading" class="hint mono">加载中…</div>
      <RouterView v-else />
    </main>

    <!-- 右下角齿轮：系统级配置（模型 / 可信源），不占导航、不打断当前页。
         带上「设置」二字：纯图标在深色角落太像窗口装饰，用户找不到入口。 -->
    <button class="gear" title="系统配置（模型 · 可信源）" @click="store.openSettings('model')">
      <span class="icon">⚙</span>
      <span class="txt">设置</span>
    </button>

    <SettingsDialog />
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  height: 100%;
}

/* 系统配置入口：固定在右下角，任何页面都够得着。
   常显「设置」二字 + 强调色描边：深色界面里纯图标会被当成窗口装饰。 */
.gear {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 40;
  display: flex;
  gap: 7px;
  align-items: center;
  padding: 9px 15px 9px 13px;
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  color: var(--flow);
  background: #16212d;
  border: 1px solid rgba(79, 209, 197, 0.5);
  border-radius: 22px;
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.45);
  transition:
    background 0.15s,
    border-color 0.15s,
    transform 0.15s;
}

.gear .icon {
  font-size: 15px;
  line-height: 1;
}

.gear:hover {
  background: rgba(79, 209, 197, 0.16);
  border-color: var(--flow);
  transform: translateY(-1px);
}

.gear:hover .icon {
  transform: rotate(35deg);
}

.side {
  display: flex;
  flex-direction: column;
  width: 224px;
  padding: 18px 14px;
  overflow-y: auto;
  background: var(--panel);
  border-right: 1px solid var(--line);
}

.brand h1 {
  font-family: 'Songti SC', 'Noto Serif SC', serif;
  font-size: 18px;
  letter-spacing: 0.5px;
}

.brand .path {
  margin-top: 6px;
  font-size: 10.5px;
  color: var(--dim);
  word-break: break-all;
}

nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 22px;
}

.item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 9px 11px;
  text-decoration: none;
  color: var(--ink);
  border: 1px solid transparent;
  border-radius: 9px;
}

.item:hover {
  border-color: var(--line);
}

.item.router-link-active {
  background: rgba(79, 209, 197, 0.08);
  border-color: rgba(79, 209, 197, 0.4);
}

.item .label {
  font-size: 14px;
  font-weight: 600;
}

.item .hint {
  font-size: 10.5px;
  color: var(--dim);
}

/* 历史：紧贴「搜索」项，视觉上是它的下级 */
.hist {
  margin: 2px 0 6px 4px;
  padding-left: 9px;
  border-left: 1px solid var(--line);
}

.hist-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 4px;
}

.hist-title {
  font-size: 10.5px;
  letter-spacing: 1px;
  color: var(--dim);
}

.hist-clear {
  padding: 1px 7px;
  font-size: 10.5px;
  color: var(--dim);
  background: transparent;
  border: 1px solid var(--line);
  border-radius: 7px;
}

.hist-clear:hover {
  color: #ffb4b4;
  border-color: #5a2a2a;
}

.hist-list {
  list-style: none;
  max-height: 260px;
  overflow-y: auto;
}

.hist-item {
  display: flex;
  gap: 6px;
  align-items: center;
  width: 100%;
  padding: 5px 6px;
  font-family: inherit;
  text-align: left;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 7px;
}

.hist-item:hover {
  background: rgba(79, 209, 197, 0.07);
  border-color: var(--line);
}

.hist-dot {
  flex: none;
  width: 5px;
  height: 5px;
  border-radius: 50%;
}

.hist-dot.on {
  background: var(--flow);
}

.hist-dot.off {
  background: var(--amber);
}

.hist-topic {
  overflow: hidden;
  font-size: 12px;
  color: var(--ink);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hist-empty {
  padding: 2px 6px 4px;
  font-size: 11px;
  color: var(--dim);
}

.foot {
  margin-top: auto;
  font-size: 11px;
  line-height: 1.9;
  color: var(--dim);
}

.foot .warn {
  color: var(--amber);
}

.body {
  flex: 1;
  min-width: 0;
  overflow: auto;
  padding: 18px 20px;
}

.err {
  padding: 12px 14px;
  border: 1px solid #5a2a2a;
  border-radius: 10px;
  color: #ffb4b4;
  font-size: 12.5px;
  line-height: 1.6;
}

.hint {
  color: var(--dim);
  font-size: 12.5px;
}
</style>
