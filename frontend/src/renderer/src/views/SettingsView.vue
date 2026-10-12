<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { SOURCE_TYPES, type SourceItem, type TrustedModule } from '../../../shared/ipc'
import { api } from '@/api'

type Filter = 'all' | 'auto' | 'manual'

const modules = ref<TrustedModule[]>([])
const filter = ref<Filter>('all')
const error = ref('')
const notice = ref('')
const busy = ref(false)

/** 新建模块 */
const newTopic = ref('')

/** 哪个模块正在展开「加源」表单 */
const addingTo = ref('')
const draft = ref<SourceItem>({ name: '', type: '规范', why: '', locator: '' })

const counts = computed(() => ({
  all: modules.value.length,
  auto: modules.value.filter(m => m.origin === 'auto').length,
  manual: modules.value.filter(m => m.origin === 'manual').length,
  sources: modules.value.reduce((n, m) => n + m.sources.length, 0)
}))

const shown = computed(() =>
  filter.value === 'all' ? modules.value : modules.value.filter(m => m.origin === filter.value)
)

function fail(e: unknown): void {
  error.value = e instanceof Error ? e.message : String(e)
}

async function refresh(): Promise<void> {
  try {
    modules.value = await api.modulesList()
  } catch (e) {
    fail(e)
  }
}

async function createModule(): Promise<void> {
  const topic = newTopic.value.trim()
  if (!topic || busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    modules.value = await api.moduleSave(topic)
    notice.value = `已新建模块「${topic}」`
    newTopic.value = ''
  } catch (e) {
    fail(e)
  } finally {
    busy.value = false
  }
}

async function removeModule(m: TrustedModule): Promise<void> {
  error.value = ''
  notice.value = ''
  try {
    modules.value = await api.moduleDelete(m.id)
    notice.value = `已删除模块「${m.topic}」`
  } catch (e) {
    fail(e)
  }
}

function openAdd(m: TrustedModule): void {
  addingTo.value = addingTo.value === m.id ? '' : m.id
  draft.value = { name: '', type: '规范', why: '', locator: '' }
}

async function addSource(m: TrustedModule): Promise<void> {
  const name = draft.value.name.trim()
  if (!name || busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    modules.value = await api.sourceAdd(m.id, {
      name,
      type: draft.value.type,
      why: draft.value.why.trim(),
      locator: draft.value.locator.trim()
    })
    notice.value = `已向「${m.topic}」添加「${name}」`
    draft.value = { name: '', type: '规范', why: '', locator: '' }
    addingTo.value = ''
  } catch (e) {
    fail(e)
  } finally {
    busy.value = false
  }
}

async function removeSource(m: TrustedModule, name: string): Promise<void> {
  error.value = ''
  notice.value = ''
  try {
    modules.value = await api.sourceRemove(m.id, name)
    notice.value = `已从「${m.topic}」删除「${name}」`
  } catch (e) {
    fail(e)
  }
}

onMounted(refresh)
</script>

<template>
  <div class="wrap">
    <h2 class="title">设置 · 可信源模块</h2>
    <p class="sub">
      可信源按主题组织成<strong>模块</strong>。搜主题时 AI
      会判定并<strong>自动收录</strong>成一个模块； 也可在这里手工新建 /
      调整。下次搜同一主题直接命中，不再重复调用模型。
    </p>

    <p v-if="error" class="msg err mono">{{ error }}</p>
    <p v-if="notice" class="msg ok mono">{{ notice }}</p>

    <div class="bar">
      <button :class="{ on: filter === 'all' }" @click="filter = 'all'">
        全部 <span class="mono">{{ counts.all }}</span>
      </button>
      <button :class="{ on: filter === 'auto' }" @click="filter = 'auto'">
        <span class="dot auto" />AI 自动 <span class="mono">{{ counts.auto }}</span>
      </button>
      <button :class="{ on: filter === 'manual' }" @click="filter = 'manual'">
        <span class="dot manual" />手工 <span class="mono">{{ counts.manual }}</span>
      </button>
      <span class="total mono">共 {{ counts.sources }} 条源</span>
    </div>

    <div class="new">
      <input
        v-model="newTopic"
        placeholder="新建模块：输入主题，例如 Rust 所有权"
        @keyup.enter="createModule"
      />
      <button class="primary" :disabled="busy || !newTopic.trim()" @click="createModule">
        新建模块
      </button>
    </div>

    <section v-for="m in shown" :key="m.id" class="module">
      <header>
        <span class="origin" :class="m.origin">
          {{ m.origin === 'auto' ? 'AI 自动' : '手工' }}
        </span>
        <h3>{{ m.topic }}</h3>
        <span class="n mono">{{ m.sources.length }} 条源</span>
        <div class="ops">
          <button @click="openAdd(m)">{{ addingTo === m.id ? '取消' : '+ 加源' }}</button>
          <button class="danger" @click="removeModule(m)">删除模块</button>
        </div>
      </header>

      <p v-if="m.keywords.length" class="kw mono">关键词：{{ m.keywords.join(' · ') }}</p>

      <ul v-if="m.sources.length" class="sources">
        <li v-for="s in m.sources" :key="s.name">
          <span class="type" :class="`t-${s.type}`">{{ s.type }}</span>
          <div class="info">
            <span class="name">{{ s.name }}</span>
            <span v-if="s.why" class="why">{{ s.why }}</span>
            <span v-if="s.locator" class="loc mono">{{ s.locator }}</span>
          </div>
          <button class="mini danger" @click="removeSource(m, s.name)">删除</button>
        </li>
      </ul>
      <p v-else class="dim none">还没有源 —— 点「+ 加源」，或去搜这个主题让 AI 自动收录。</p>

      <div v-if="addingTo === m.id" class="add">
        <input v-model="draft.name" placeholder="来源名称（必填）" @keyup.enter="addSource(m)" />
        <select v-model="draft.type">
          <option v-for="t in SOURCE_TYPES" :key="t" :value="t">{{ t }}</option>
        </select>
        <input v-model="draft.locator" placeholder="定位（链接 / ISBN / 仓库）" />
        <input v-model="draft.why" placeholder="为什么可信" @keyup.enter="addSource(m)" />
        <button class="primary" :disabled="busy || !draft.name.trim()" @click="addSource(m)">
          保存
        </button>
      </div>
    </section>

    <p v-if="!shown.length" class="dim empty">
      {{
        modules.length
          ? '该分类下暂无模块。'
          : '还没有模块：上方新建，或去「搜索主题」让 AI 自动收录。'
      }}
    </p>
  </div>
</template>

<style scoped>
.wrap {
  max-width: 900px;
}

.title {
  font-family: 'Songti SC', 'Noto Serif SC', serif;
  font-size: 21px;
}

.sub {
  margin-top: 6px;
  font-size: 12.5px;
  line-height: 1.75;
  color: var(--dim);
}

.sub strong {
  color: var(--ink);
}

.msg {
  margin-top: 12px;
  padding: 9px 12px;
  font-size: 12.5px;
  border-radius: 9px;
}

.err {
  color: #ffb4b4;
  border: 1px solid #5a2a2a;
}

.ok {
  color: var(--flow);
  border: 1px solid rgba(79, 209, 197, 0.4);
}

.bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 16px;
}

.bar button {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot.auto {
  background: var(--amber);
}

.dot.manual {
  background: var(--flow);
}

.total {
  margin-left: auto;
  font-size: 11.5px;
  color: var(--dim);
}

.new {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}

.new input {
  flex: 1;
  padding: 9px 12px;
  font-family: inherit;
  font-size: 13px;
  color: var(--ink);
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
}

.new input:focus,
.add input:focus,
.add select:focus {
  outline: none;
  border-color: var(--flow);
}

button.primary {
  font-weight: 600;
  color: #06282a;
  background: var(--flow);
  border-color: var(--flow);
}

button.primary:disabled {
  opacity: 0.45;
  cursor: default;
}

.module {
  margin-top: 14px;
  padding: 14px 16px 16px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 12px;
}

.module header {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.module h3 {
  font-size: 15px;
}

.origin {
  padding: 1px 8px;
  font-size: 10.5px;
  font-weight: 700;
  color: #0b0e13;
  border-radius: 8px;
}

.origin.auto {
  background: var(--amber);
}

.origin.manual {
  background: var(--flow);
}

.n {
  font-size: 11px;
  color: var(--dim);
}

.module .ops {
  display: flex;
  gap: 7px;
  margin-left: auto;
}

.module .ops button,
button.mini {
  padding: 4px 10px;
  font-size: 11.5px;
}

button.danger:hover {
  color: #ffb4b4;
  border-color: #5a2a2a;
}

.kw {
  margin-top: 8px;
  font-size: 11px;
  color: var(--dim);
}

.sources {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 12px;
}

.sources li {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 9px 11px;
  background: #0f1620;
  border-radius: 9px;
}

.type {
  padding: 1px 8px;
  font-size: 10.5px;
  font-weight: 700;
  color: #0b0e13;
  background: var(--dim);
  border-radius: 8px;
  white-space: nowrap;
}

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

.info {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.info .name {
  font-size: 13.5px;
  font-weight: 600;
}

.info .why {
  font-size: 11.5px;
  color: var(--dim);
}

.info .loc {
  font-size: 11px;
  color: #6ea8fe;
  word-break: break-all;
}

.add {
  display: grid;
  grid-template-columns: 1fr 110px;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--line);
}

.add input,
.add select {
  padding: 8px 10px;
  font-family: inherit;
  font-size: 12.5px;
  color: var(--ink);
  background: #0f1620;
  border: 1px solid var(--line);
  border-radius: 8px;
}

.add button {
  grid-column: 1 / -1;
  justify-self: start;
  padding: 7px 18px;
}

.dim {
  color: var(--dim);
}

.none,
.empty {
  font-size: 12.5px;
}

.none {
  margin-top: 10px;
}

.empty {
  margin-top: 24px;
}
</style>
