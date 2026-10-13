<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  SOURCE_TYPES,
  type ModuleOrigin,
  type SourceEntry,
  type TrustedModule,
  type TrustedSource,
  type TrustedSourceInput
} from '../../../shared/ipc'
import { api } from '@/api'

type Filter = 'all' | 'auto' | 'manual'

const modules = ref<TrustedModule[]>([])
const platforms = ref<TrustedSource[]>([])
const filter = ref<Filter>('all')
const error = ref('')
const notice = ref('')
const busy = ref(false)

/** 新建模块 */
const newTopic = ref('')
/** 新建可信源（平台） */
const addingPlatform = ref(false)
const draftPlatform = ref<TrustedSourceInput>({ name: '', type: '规范', why: '', home: '' })
/** 哪个模块正在展开「加条目」表单 */
const addingTo = ref('')
const draftEntry = ref<SourceEntry>({ title: '', source: '', locator: '', note: '' })

const ORIGIN_LABEL: Record<string, string> = {
  builtin: '内置',
  auto: 'AI 收录',
  manual: '手工'
}

const platformById = computed(() => new Map(platforms.value.map(p => [p.id, p])))

function platformName(id: string): string {
  return platformById.value.get(id)?.name ?? '未登记来源'
}

const counts = computed(() => ({
  all: modules.value.length,
  auto: modules.value.filter(m => m.origin === 'auto').length,
  manual: modules.value.filter(m => m.origin === 'manual').length,
  entries: modules.value.reduce((n, m) => n + m.items.length, 0)
}))

const shown = computed(() =>
  filter.value === 'all' ? modules.value : modules.value.filter(m => m.origin === filter.value)
)

function fail(e: unknown): void {
  error.value = e instanceof Error ? e.message : String(e)
}

async function refresh(): Promise<void> {
  try {
    const [mods, srcs] = await Promise.all([api.modulesList(), api.platformsList()])
    modules.value = mods
    platforms.value = srcs
  } catch (e) {
    fail(e)
  }
}

// ---------- 可信源（平台）----------

async function addPlatform(): Promise<void> {
  const name = draftPlatform.value.name.trim()
  if (!name || busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const res = await api.platformAdd({
      name,
      type: draftPlatform.value.type,
      why: draftPlatform.value.why.trim(),
      home: draftPlatform.value.home.trim()
    })
    platforms.value = res.platforms
    // 归一后可能落到已有平台上（同一个站）：如实说清，别让用户以为自己建了个新的
    notice.value =
      res.platform.name === name
        ? `已保存可信源「${res.platform.name}」（id ${res.platform.id}）`
        : `「${name}」与已有平台同站，已归入「${res.platform.name}」（id ${res.platform.id}）`
    draftPlatform.value = { name: '', type: '规范', why: '', home: '' }
    addingPlatform.value = false
  } catch (e) {
    fail(e)
  } finally {
    busy.value = false
  }
}

async function removePlatform(p: TrustedSource): Promise<void> {
  error.value = ''
  notice.value = ''
  try {
    platforms.value = await api.platformRemove(p.id)
    notice.value = `已删除可信源「${p.name}」`
  } catch (e) {
    fail(e)
  }
}

// ---------- 主题模块 / 条目 ----------

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
  const open = addingTo.value !== m.id
  addingTo.value = open ? m.id : ''
  // 默认选中模块已引用的第一个平台，省一次下拉
  const first = m.items.find(e => platformById.value.has(e.source))?.source
  draftEntry.value = {
    title: '',
    source: first ?? platforms.value[0]?.id ?? '',
    locator: '',
    note: ''
  }
}

async function addEntry(m: TrustedModule): Promise<void> {
  const title = draftEntry.value.title.trim()
  if (!title || busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    modules.value = await api.entryAdd(m.id, {
      title,
      source: draftEntry.value.source,
      locator: draftEntry.value.locator.trim(),
      note: draftEntry.value.note.trim()
    })
    notice.value = `已向「${m.topic}」添加条目「${title}」`
    draftEntry.value = { title: '', source: draftEntry.value.source, locator: '', note: '' }
    addingTo.value = ''
  } catch (e) {
    fail(e)
  } finally {
    busy.value = false
  }
}

async function removeEntry(m: TrustedModule, e: SourceEntry): Promise<void> {
  error.value = ''
  notice.value = ''
  try {
    modules.value = await api.entryRemove(m.id, e.title)
    notice.value = `已从「${m.topic}」删除条目「${e.title}」`
  } catch (err) {
    fail(err)
  }
}

function moduleOriginLabel(origin: ModuleOrigin): string {
  return origin === 'auto' ? 'AI 自动' : '手工'
}

onMounted(refresh)
</script>

<template>
  <div class="wrap">
    <p class="sub">
      可信源分<strong>两层</strong>：<strong>平台</strong>（GitHub / arXiv
      这种泛化出处，跨主题复用，
      全局一份）与<strong>条目</strong>（某平台上具体哪个文件，挂在主题模块下）。搜主题时 AI
      按这个结构判定并<strong>自动收录</strong>，也可以在这里手工调。
    </p>

    <p v-if="error" class="msg err mono">{{ error }}</p>
    <p v-if="notice" class="msg ok mono">{{ notice }}</p>

    <!-- 第一层：可信源（平台） -->
    <section class="layer">
      <header class="layer-head">
        <h3>可信源（平台）</h3>
        <span class="n mono">{{ platforms.length }} 个</span>
        <div class="ops">
          <button @click="addingPlatform = !addingPlatform">
            {{ addingPlatform ? '取消' : '+ 新增平台' }}
          </button>
        </div>
      </header>
      <p class="hint">
        id 由<strong>宿主域名</strong>归一（github.com）——同一个站无论怎么写都只算一个平台，
        这是「可信源不爆炸」的保证。内置平台改自 <code>config/sources.yml</code>，删不掉。
      </p>

      <div v-if="addingPlatform" class="add">
        <input
          v-model="draftPlatform.name"
          placeholder="平台名（GitHub / arXiv / MDN…）"
          @keyup.enter="addPlatform"
        />
        <select v-model="draftPlatform.type">
          <option v-for="t in SOURCE_TYPES" :key="t" :value="t">{{ t }}</option>
        </select>
        <input v-model="draftPlatform.home" placeholder="平台入口 URL（决定归一 id）" />
        <input
          v-model="draftPlatform.why"
          placeholder="为什么这个平台可信（跨主题成立）"
          @keyup.enter="addPlatform"
        />
        <button class="primary" :disabled="busy || !draftPlatform.name.trim()" @click="addPlatform">
          保存
        </button>
      </div>

      <ul class="platforms">
        <li v-for="p in platforms" :key="p.id">
          <span class="type" :class="`t-${p.type}`">{{ p.type }}</span>
          <div class="info">
            <span class="name">
              {{ p.name }}
              <span class="pid mono">{{ p.id }}</span>
              <span class="origin mono">{{ ORIGIN_LABEL[p.origin] ?? p.origin }}</span>
            </span>
            <span v-if="p.why" class="why">{{ p.why }}</span>
            <span v-if="p.home" class="loc mono">{{ p.home }}</span>
          </div>
          <span v-if="p.origin === 'builtin'" class="keep mono">内置</span>
          <button v-else class="mini danger" @click="removePlatform(p)">删除</button>
        </li>
      </ul>
    </section>

    <!-- 第二层：主题模块（条目） -->
    <section class="layer">
      <header class="layer-head">
        <h3>主题模块（条目）</h3>
        <span class="n mono">{{ counts.all }} 个模块 · {{ counts.entries }} 条条目</span>
      </header>
      <p class="hint">模块按 topic 组织；搜过同一主题直接命中，不再调模型。</p>

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

      <article v-for="m in shown" :key="m.id" class="module">
        <header>
          <span class="origin" :class="m.origin">
            {{ moduleOriginLabel(m.origin) }}
          </span>
          <h3>{{ m.topic }}</h3>
          <span class="n mono">{{ m.items.length }} 条条目</span>
          <div class="ops">
            <button @click="openAdd(m)">{{ addingTo === m.id ? '取消' : '+ 加条目' }}</button>
            <button class="danger" @click="removeModule(m)">删除模块</button>
          </div>
        </header>

        <p v-if="m.keywords.length" class="kw mono">关键词：{{ m.keywords.join(' · ') }}</p>

        <ul v-if="m.items.length" class="entries">
          <li v-for="e in m.items" :key="`${e.title}|${e.locator}`">
            <span class="from mono">{{ platformName(e.source) }}</span>
            <div class="info">
              <span class="title">{{ e.title }}</span>
              <span v-if="e.note" class="why">{{ e.note }}</span>
              <span v-if="e.locator" class="loc mono">{{ e.locator }}</span>
            </div>
            <button class="mini danger" @click="removeEntry(m, e)">删除</button>
          </li>
        </ul>
        <p v-else class="dim none">还没有条目 —— 点「+ 加条目」，或去搜这个主题让 AI 自动收录。</p>

        <div v-if="addingTo === m.id" class="add">
          <input
            v-model="draftEntry.title"
            placeholder="条目标题（必填）"
            @keyup.enter="addEntry(m)"
          />
          <select v-model="draftEntry.source">
            <option value="">（未指定平台）</option>
            <option v-for="p in platforms" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <input v-model="draftEntry.locator" placeholder="具体定位（URL / ISBN+章节）" />
          <input
            v-model="draftEntry.note"
            placeholder="这条为什么值得读"
            @keyup.enter="addEntry(m)"
          />
          <button class="primary" :disabled="busy || !draftEntry.title.trim()" @click="addEntry(m)">
            保存
          </button>
        </div>
      </article>

      <p v-if="!shown.length" class="dim empty">
        {{
          modules.length
            ? '该分类下暂无模块。'
            : '还没有模块：上方新建，或去「搜索主题」让 AI 自动收录。'
        }}
      </p>
    </section>
  </div>
</template>

<style scoped>
.wrap {
  max-width: none;
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

.layer {
  margin-top: 18px;
  padding: 14px 16px 16px;
  border: 1px solid var(--line);
  border-radius: 12px;
}

.layer-head {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.layer-head h3 {
  font-size: 15px;
}

.layer-head .ops {
  display: flex;
  gap: 7px;
  margin-left: auto;
}

.layer-head .ops button {
  padding: 4px 10px;
  font-size: 11.5px;
}

.hint {
  margin-top: 8px;
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--dim);
}

.hint code {
  padding: 0 4px;
  font-size: 11px;
  background: #0f1620;
  border-radius: 4px;
}

.bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 14px;
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

.new {
  display: flex;
  gap: 10px;
  margin-top: 12px;
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

/* ---------- 平台列表（第一层） ---------- */

.platforms {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 12px;
}

.platforms li {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 9px 11px;
  background: #0f1620;
  border-radius: 9px;
}

.type,
.from {
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

.pid {
  margin-left: 6px;
  font-size: 10.5px;
  font-weight: 400;
  color: var(--dim);
}

.origin {
  padding: 1px 7px;
  font-size: 10.5px;
  font-weight: 700;
  color: #0b0e13;
  border-radius: 7px;
  background: var(--dim);
}

.origin.auto {
  background: var(--amber);
}

.origin.manual {
  background: var(--flow);
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

.keep {
  font-size: 10.5px;
  color: var(--dim);
}

button.mini {
  padding: 4px 10px;
  font-size: 11.5px;
}

button.danger:hover {
  color: #ffb4b4;
  border-color: #5a2a2a;
}

/* ---------- 模块（第二层） ---------- */

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

.n {
  font-size: 11px;
  color: var(--dim);
}

.module .ops {
  display: flex;
  gap: 7px;
  margin-left: auto;
}

.module .ops button {
  padding: 4px 10px;
  font-size: 11.5px;
}

.kw {
  margin-top: 8px;
  font-size: 11px;
  color: var(--dim);
}

.entries {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 12px;
}

.entries li {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 9px 11px;
  background: #0f1620;
  border-radius: 9px;
}

.entries .from {
  font-weight: 400;
  color: var(--flow);
  background: transparent;
  border: 1px solid rgba(79, 209, 197, 0.35);
}

.entries .title {
  font-size: 13px;
  font-weight: 600;
}

.add {
  display: grid;
  grid-template-columns: 1fr 150px;
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
