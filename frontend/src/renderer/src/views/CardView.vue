<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { marked } from 'marked'

import type { CardDetail } from '../../../shared/ipc'
import { api } from '@/api'

const route = useRoute()
const card = ref<CardDetail | null>(null)
const error = ref('')

/** 卡片是 L3 的「血肉」：markdown 正文 + `[[实体]]` 双链（转成可点跳转后再渲染） */
const html = computed(() => {
  if (!card.value) return ''
  const body = card.value.markdown
    .replace(/^---\s*\n[\s\S]*?\n---\s*\n/, '') // 去 frontmatter（已在头部单独展示）
    .replace(/^#\s+.*\n/, '') // 去首个 H1（标题已单独展示）
  const linked = body.replace(
    /\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]/g,
    (_m, target: string, label?: string) =>
      `[${(label ?? target).trim()}](#/cards/${target.trim()})`
  )
  return marked.parse(linked) as string
})

onMounted(async () => {
  try {
    card.value = await api.cardRead(String(route.params.key))
    if (!card.value) error.value = `找不到卡片：${String(route.params.key)}`
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
})
</script>

<template>
  <div class="wrap">
    <RouterLink to="/cards" class="back mono">← 实体卡列表</RouterLink>

    <p v-if="error" class="err mono">{{ error }}</p>

    <template v-else-if="card">
      <div class="head">
        <span class="tag">{{ card.domain || '未归域' }}</span>
        <span class="mono dim">{{ card.type }}</span>
      </div>
      <h2>{{ card.name }}</h2>
      <p v-if="card.oneLine" class="one">{{ card.oneLine }}</p>
      <p class="mono dim key">data/wiki/notes/{{ card.key }}.md</p>

      <article class="md" v-html="html" />
    </template>

    <p v-else class="dim">加载中…</p>
  </div>
</template>

<style scoped>
.wrap {
  max-width: 820px;
}

.back {
  font-size: 12px;
  color: var(--dim);
  text-decoration: none;
}

.back:hover {
  color: var(--flow);
}

.head {
  display: flex;
  gap: 9px;
  align-items: center;
  margin-top: 14px;
}

.tag {
  padding: 2px 9px;
  border-radius: 9px;
  font-size: 11px;
  font-weight: 700;
  color: #0b0e13;
  background: var(--flow);
}

h2 {
  margin: 6px 0 4px;
  font-size: 20px;
}

.one {
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--ink);
}

.key {
  margin-top: 6px;
  font-size: 11.5px;
}

.md {
  margin-top: 18px;
  padding: 20px 22px;
  line-height: 1.75;
  color: var(--ink);
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 12px;
}

.md :deep(h1),
.md :deep(h2) {
  margin: 18px 0 8px;
  font-size: 16px;
  color: var(--flow);
}

.md :deep(h1:first-child),
.md :deep(h2:first-child) {
  margin-top: 0;
}

.md :deep(h3) {
  margin: 14px 0 6px;
  font-size: 14px;
}

.md :deep(p) {
  margin: 8px 0;
  font-size: 13.5px;
}

.md :deep(ul),
.md :deep(ol) {
  margin: 8px 0;
  padding-left: 20px;
  font-size: 13.5px;
}

.md :deep(li) {
  margin: 3px 0;
}

.md :deep(code) {
  padding: 1px 6px;
  font-family: ui-monospace, Menlo, monospace;
  font-size: 12px;
  color: #79c0ff;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 4px;
}

.md :deep(pre) {
  margin: 10px 0;
  padding: 12px 14px;
  overflow-x: auto;
  background: #0f1620;
  border: 1px solid var(--line);
  border-radius: 8px;
}

.md :deep(pre code) {
  padding: 0;
  color: var(--ink);
  background: none;
}

.md :deep(a) {
  color: var(--flow);
  text-decoration: none;
  border-bottom: 1px dashed rgba(79, 209, 197, 0.5);
}

.md :deep(a:hover) {
  border-bottom-style: solid;
}

.md :deep(hr) {
  margin: 16px 0;
  border: none;
  border-top: 1px solid var(--line);
}

.md :deep(blockquote) {
  margin: 10px 0;
  padding: 8px 14px;
  color: var(--dim);
  border-left: 3px solid var(--line);
}

.dim {
  color: var(--dim);
  font-size: 12.5px;
}

.err {
  padding: 10px 12px;
  border: 1px solid #5a2a2a;
  border-radius: 9px;
  color: #ffb4b4;
  font-size: 12.5px;
}
</style>
