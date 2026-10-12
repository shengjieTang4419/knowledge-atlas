<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import type { SearchResult } from '../../../shared/ipc'
import { api } from '@/api'

const router = useRouter()
const topic = ref('')
const result = ref<SearchResult | null>(null)
const loading = ref(false)
const error = ref('')

/** 来源出处徽章（内置 / 我的配置 / 模型候选） */
const ORIGIN_LABEL: Record<string, string> = {
  builtin: '内置模块',
  auto: 'AI 自动收录',
  manual: '手工配置',
  user: '手工配置',
  llm: '模型候选（未收录）'
}

/**
 * 没匹配上时的提示口径，分三种：
 * - 没配 LLM：解释「为什么没自动生成」+ 引导手工建模块
 * - 有 LLM 但模型没给出：引导手工补充
 * - 已有模块但都不匹配：提示补充相关来源
 */
const emptyHint = computed(() => {
  const r = result.value
  if (!r) return ''
  const n = r.moduleCount
  if (!r.llmAvailable) {
    return n === 0
      ? '未找到可信源。当前没配 AI 模型 Key，无法自动判定；可在设置里手工新建模块并添加来源。'
      : `未找到可信源。已建 ${n} 个模块但都不匹配该主题；也可在设置里补充，或配好 AI 模型 Key 后自动判定收录。`
  }
  return n === 0
    ? 'AI 这次没能给出可信源。可在设置里手工新建模块添加来源。'
    : `AI 没能给出新来源，已有 ${n} 个模块也都不匹配该主题。去设置里补充相关来源。`
})

async function run(): Promise<void> {
  const q = topic.value.trim()
  if (!q || loading.value) return
  loading.value = true
  error.value = ''
  try {
    result.value = await api.searchTopic(q)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
    result.value = null
  } finally {
    loading.value = false
  }
}

function gotoSettings(): void {
  void router.push('/settings')
}

onMounted(run)
</script>

<template>
  <div class="wrap">
    <h2 class="title">搜索主题</h2>
    <p class="sub">给一个主题，得到检索关键词与相对可信的来源（规范 · 源码优先）。</p>

    <div class="bar">
      <input
        v-model="topic"
        placeholder="例如：Java 多线程 · 内存可见性"
        :disabled="loading"
        @keyup.enter="run"
      />
      <button class="primary" :disabled="loading || !topic.trim()" @click="run">
        {{ loading ? '搜索中…' : '搜索' }}
      </button>
    </div>

    <p v-if="error" class="err mono">{{ error }}</p>

    <template v-if="result && result.topic">
      <section class="block">
        <h3>检索关键词</h3>
        <div class="chips">
          <span v-for="k in result.keywords" :key="k" class="chip">{{ k }}</span>
        </div>
      </section>

      <!-- 命中：列出来源 -->
      <section v-if="result.matched" class="block">
        <div v-if="result.autoCollected" class="collected">
          <span class="badge">已自动收录</span>
          AI 判定的来源已存成一个模块，下次搜「{{ result.topic }}」直接命中，不再调用模型。
          <button class="link" @click="gotoSettings">去设置里看看</button>
        </div>
        <h3>
          可信来源
          <span class="count mono">{{ result.sources.length }} 条</span>
        </h3>
        <ul class="srcs">
          <li v-for="s in result.sources" :key="s.name">
            <div class="src-head">
              <span class="type" :class="`t-${s.type}`">{{ s.type }}</span>
              <span class="name">{{ s.name }}</span>
              <span class="origin mono">{{ ORIGIN_LABEL[s.origin] ?? s.origin }}</span>
            </div>
            <p v-if="s.why" class="why">{{ s.why }}</p>
            <a v-if="s.locator" class="loc mono" :href="s.locator" target="_blank" rel="noreferrer">
              {{ s.locator }}
            </a>
          </li>
        </ul>
      </section>

      <!-- 未命中：提示去配置（你要的那步） -->
      <section v-else-if="result.needsConfig" class="block empty">
        <div class="empty-icon">⚠</div>
        <h3>没有匹配的可信源</h3>
        <p class="empty-text">{{ emptyHint }}</p>
        <button class="primary" @click="gotoSettings">去设置里配置可信源</button>
      </section>
    </template>

    <p v-else-if="!loading && !error" class="hint dim">输入主题后回车即可搜索（回车也行）。</p>
  </div>
</template>

<style scoped>
.wrap {
  max-width: 880px;
}

.title {
  font-family: 'Songti SC', 'Noto Serif SC', serif;
  font-size: 21px;
}

.sub {
  margin-top: 6px;
  font-size: 12.5px;
  color: var(--dim);
}

.bar {
  display: flex;
  gap: 10px;
  margin-top: 18px;
}

.bar input {
  flex: 1;
  padding: 10px 13px;
  font-family: inherit;
  font-size: 14px;
  color: var(--ink);
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 9px;
}

.bar input:focus {
  outline: none;
  border-color: var(--flow);
}

button.primary {
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 600;
  color: #06282a;
  background: var(--flow);
  border-color: var(--flow);
}

button.primary:disabled {
  opacity: 0.45;
  cursor: default;
}

.block {
  margin-top: 24px;
}

.block h3 {
  margin-bottom: 10px;
  font-size: 13px;
  letter-spacing: 1px;
  color: var(--dim);
}

.count {
  margin-left: 8px;
  font-size: 11px;
  color: var(--flow);
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.chip {
  padding: 4px 11px;
  font-size: 12.5px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
}

.srcs {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.srcs li {
  padding: 12px 14px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 10px;
}

.src-head {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  align-items: center;
}

.src-head .name {
  font-size: 14px;
  font-weight: 600;
}

.type {
  padding: 1px 8px;
  font-size: 11px;
  font-weight: 700;
  color: #0b0e13;
  background: var(--dim);
  border-radius: 8px;
}

/* 可信度配色：规范/源码最高 → 社区最低 */
.t-规范,
.t-源码 {
  background: var(--flow);
}

.t-书籍,
.t-论文 {
  background: #6ea8fe;
}

.t-博客 {
  background: var(--amber);
}

.t-社区 {
  background: var(--dim);
}

.origin {
  margin-left: auto;
  font-size: 10.5px;
  color: var(--dim);
}

.why {
  margin-top: 6px;
  font-size: 12.5px;
  color: var(--dim);
}

.loc {
  display: inline-block;
  margin-top: 5px;
  font-size: 11.5px;
  color: #6ea8fe;
  text-decoration: none;
  word-break: break-all;
}

.loc:hover {
  text-decoration: underline;
}

.empty {
  padding: 26px 22px;
  text-align: center;
  background: rgba(232, 163, 61, 0.05);
  border: 1px dashed rgba(232, 163, 61, 0.45);
  border-radius: 12px;
}

.empty-icon {
  font-size: 22px;
  color: var(--amber);
}

.empty h3 {
  margin: 8px 0 0;
  font-size: 16px;
  letter-spacing: 0;
  color: var(--ink);
}

.empty-text {
  max-width: 460px;
  margin: 8px auto 16px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--dim);
}

.collected {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 14px;
  padding: 10px 13px;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--dim);
  background: rgba(79, 209, 197, 0.06);
  border: 1px solid rgba(79, 209, 197, 0.35);
  border-radius: 10px;
}

.collected .badge {
  padding: 1px 8px;
  font-size: 11px;
  font-weight: 700;
  color: #06282a;
  background: var(--flow);
  border-radius: 8px;
}

.collected .link {
  padding: 2px 9px;
  font-size: 11.5px;
}

.err {
  margin-top: 14px;
  padding: 10px 12px;
  font-size: 12.5px;
  color: #ffb4b4;
  border: 1px solid #5a2a2a;
  border-radius: 9px;
}

.dim {
  color: var(--dim);
}

.hint {
  margin-top: 22px;
  font-size: 12.5px;
}
</style>
