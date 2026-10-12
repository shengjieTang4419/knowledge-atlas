<script setup lang="ts">
import { onMounted, ref } from 'vue'

import type { MechCard } from '../../../shared/ipc'
import { api } from '@/api'

const cards = ref<MechCard[]>([])
const error = ref('')

onMounted(async () => {
  try {
    cards.value = await api.mechCardsList()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
})
</script>

<template>
  <div>
    <div class="bar">
      <h2>机制卡 · 金线</h2>
      <span class="mono dim">{{ cards.length }} 张</span>
    </div>
    <p class="sub dim">把可迁移的「解法动作」从语境抽象出来。类比 = 两个实体共享同一张卡（非边）。</p>

    <p v-if="error" class="err mono">{{ error }}</p>

    <div class="grid">
      <article v-for="c in cards" :key="c.name" class="card">
        <h3>{{ c.name }}</h3>
        <dl>
          <div v-if="c.problem"><dt>问题形态</dt><dd>{{ c.problem }}</dd></div>
          <div v-if="c.mechanism"><dt>核心机制</dt><dd>{{ c.mechanism }}</dd></div>
          <div v-if="c.tradeoff"><dt>权衡</dt><dd>{{ c.tradeoff }}</dd></div>
          <div v-if="c.boundary"><dt>适用边界</dt><dd>{{ c.boundary }}</dd></div>
        </dl>
        <div class="cases">
          <span v-for="cs in c.cases" :key="cs" class="chip">{{ cs }}</span>
        </div>
      </article>
    </div>

    <p v-if="!cards.length && !error" class="dim">data/mechanism/cards.md 下暂无机制卡</p>
  </div>
</template>

<style scoped>
.bar {
  display: flex;
  gap: 12px;
  align-items: baseline;
}

.bar h2 {
  font-family: 'Songti SC', 'Noto Serif SC', serif;
  font-size: 18px;
}

.sub {
  margin-top: 4px;
  font-size: 12.5px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.card {
  padding: 14px 16px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 12px;
}

.card:hover {
  border-color: var(--amber);
}

.card h3 {
  font-size: 15px;
  color: var(--amber);
  margin-bottom: 10px;
}

dl {
  font-size: 12.5px;
  line-height: 1.6;
}

dl > div {
  margin-bottom: 6px;
}

dt {
  display: inline;
  color: var(--dim);
  margin-right: 6px;
}

dd {
  display: inline;
  color: var(--ink);
}

.cases {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--line);
}

.chip {
  display: inline-block;
  margin: 0 6px 4px 0;
  padding: 2px 8px;
  border: 1px solid rgba(232, 163, 61, 0.4);
  border-radius: 8px;
  font-size: 11.5px;
  color: #e8b05c;
}

.dim {
  color: var(--dim);
}

.err {
  padding: 10px 12px;
  margin-top: 12px;
  border: 1px solid #5a2a2a;
  border-radius: 9px;
  color: #ffb4b4;
  font-size: 12.5px;
}
</style>
