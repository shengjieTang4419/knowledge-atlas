<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import type { CardMeta } from '../../../shared/ipc'
import { api } from '@/api'

const cards = ref<CardMeta[]>([])
const keyword = ref('')
const error = ref('')

onMounted(async () => {
  try {
    cards.value = await api.cardsList()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
})

const grouped = computed(() => {
  const kw = keyword.value.trim()
  const hit = kw
    ? cards.value.filter(c => `${c.name} ${c.key} ${c.domain} ${c.oneLine}`.includes(kw))
    : cards.value
  const out: Record<string, CardMeta[]> = {}
  for (const c of hit) {
    ;(out[c.domain || '（未归域）'] ||= []).push(c)
  }
  return out
})
</script>

<template>
  <div>
    <div class="bar">
      <input v-model="keyword" placeholder="搜索实体 / 领域…" />
      <span class="mono dim">{{ cards.length }} 张卡片</span>
    </div>

    <p v-if="error" class="err mono">{{ error }}</p>

    <section v-for="(list, domain) in grouped" :key="domain" class="group">
      <h2>{{ domain }}</h2>
      <div class="grid">
        <RouterLink v-for="c in list" :key="c.key" :to="`/cards/${c.key}`" class="card">
          <span class="name">{{ c.name }}</span>
          <span class="type mono">{{ c.type }}</span>
          <span v-if="c.oneLine" class="one">{{ c.oneLine }}</span>
        </RouterLink>
      </div>
    </section>

    <p v-if="!cards.length && !error" class="dim">data/wiki/notes/ 下暂无卡片</p>
  </div>
</template>

<style scoped>
.bar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.bar input {
  width: 300px;
  padding: 7px 11px;
  color: var(--ink);
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  font-family: inherit;
  font-size: 13px;
}

.bar input:focus {
  outline: none;
  border-color: var(--flow);
}

.dim {
  color: var(--dim);
  font-size: 12px;
}

.group {
  margin-top: 22px;
}

.group h2 {
  margin-bottom: 10px;
  font-family: 'Songti SC', 'Noto Serif SC', serif;
  font-size: 16px;
  color: var(--flow);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}

.card {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 12px 13px;
  text-decoration: none;
  color: var(--ink);
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 10px;
}

.card:hover {
  border-color: var(--flow);
}

.card .name {
  font-size: 14px;
  font-weight: 600;
}

.card .type {
  font-size: 10.5px;
  color: var(--dim);
}

.card .one {
  font-size: 12px;
  line-height: 1.5;
  color: var(--dim);
}

.err {
  padding: 10px 12px;
  border: 1px solid #5a2a2a;
  border-radius: 9px;
  color: #ffb4b4;
  font-size: 12.5px;
}
</style>
