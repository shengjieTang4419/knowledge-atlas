<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink, RouterView } from 'vue-router'

import { useAtlasStore } from '@/stores/atlas'

const store = useAtlasStore()
onMounted(() => void store.loadAll())

/** 菜单按设计文档的分层组织（L1·L2 输入 / L3 结构 / L4 迁移 / 系统） */
const nav = [
  { to: '/search', label: '搜索', hint: 'L1·L2 · 主题 → 可信源' },
  { to: '/graph', label: '图谱层', hint: 'L3 · 实体与关系' },
  { to: '/cards', label: '实体卡', hint: 'L3 · 血肉文档（markdown）' },
  { to: '/mechanism', label: '知识层', hint: 'L4 · 机制卡（金线）' },
  { to: '/settings', label: '设置', hint: '可信源模块' },
  { to: '/cli', label: '跑层', hint: 'CLI · 逐层调试' }
]
</script>

<template>
  <div class="shell">
    <aside class="side">
      <div class="brand">
        <h1>Knowledge Atlas</h1>
        <p class="mono path">{{ store.repoRoot || '未定位仓库根' }}</p>
      </div>

      <nav>
        <RouterLink v-for="n in nav" :key="n.to" :to="n.to" class="item">
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
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  height: 100%;
}

.side {
  display: flex;
  flex-direction: column;
  width: 224px;
  padding: 18px 14px;
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
