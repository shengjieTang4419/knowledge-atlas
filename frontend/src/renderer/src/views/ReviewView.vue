<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { CommitResult, DraftEdge, DraftPreview } from '../../../shared/ipc'
import { api } from '@/api'
import { useAtlasStore } from '@/stores/atlas'

const route = useRoute()
const router = useRouter()
const store = useAtlasStore()

const topic = ref('')
const loading = ref(true)
const error = ref('')
const draft = ref<DraftPreview | null>(null)
const committing = ref(false)
const committed = ref<CommitResult | null>(null)

/** 逐项勾选：默认全选；人取消即不写入 */
const entityOn = ref<boolean[]>([])
const cardOn = ref<boolean[]>([])
const edgeOn = ref<boolean[]>([])

function norm(s: string): string {
  return s.replace(/\s+/g, '').toLowerCase()
}

const selectedCount = computed(() => ({
  entities: entityOn.value.filter(Boolean).length,
  cards: cardOn.value.filter(Boolean).length,
  edges: edgeOn.value.filter(Boolean).length
}))

/** 边按类型分两组展示，但勾选状态始终挂在原始下标上（不重排丢索引） */
const edgeItems = computed(() =>
  (draft.value?.edges ?? []).map((edge: DraftEdge, index: number) => ({ edge, index }))
)
const progressItems = computed(() => edgeItems.value.filter(x => x.edge.type === '递进'))
const applyItems = computed(() => edgeItems.value.filter(x => x.edge.type === '应用'))

onMounted(async () => {
  topic.value = typeof route.query.topic === 'string' ? route.query.topic : ''
  if (!topic.value) {
    loading.value = false
    error.value = '缺少主题参数，请从搜索页进入。'
    return
  }
  try {
    draft.value = await api.draftTopic(topic.value)
    entityOn.value = draft.value.entities.map(() => true)
    cardOn.value = draft.value.cards.map(() => true)
    edgeOn.value = draft.value.edges.map(() => true)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
})

/** 模板里 ref 会自动解包，故按数组原地改（保持响应性） */
function toggleAll(on: boolean[], value: boolean): void {
  for (let i = 0; i < on.length; i++) on[i] = value
}

function backToSearch(): void {
  void router.push('/search')
}

function goSettings(): void {
  // 开弹层而不是跳页：跳走会丢掉当前草稿，回来还得重跑一遍模型
  store.openSettings('sources')
}

async function commit(): Promise<void> {
  const d = draft.value
  if (!d || committing.value) return
  committing.value = true
  try {
    const selectedEntities = d.entities.filter((_, i) => entityOn.value[i])
    const selectedCards = d.cards.filter((_, i) => cardOn.value[i])
    const selectedEdges = d.edges.filter((_, i) => edgeOn.value[i])
    // 关系只在两端实体都被选中时写入（避免指向未建卡的断链）
    const names = new Set(selectedEntities.map(e => norm(e.name)))
    const relations = d.relations.filter(r => names.has(norm(r.src)) && names.has(norm(r.dst)))
    committed.value = await api.commitDraft({
      ...d,
      entities: selectedEntities,
      cards: selectedCards,
      edges: selectedEdges,
      relations
    })
    await store.loadAll()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    committing.value = false
  }
}
</script>

<template>
  <div class="wrap">
    <p v-if="loading" class="dim">正在生成预览（L1→L4 预演，不写盘）…</p>

    <p v-else-if="error" class="err mono">{{ error }}</p>

    <div v-else-if="committed" class="done">
      <h2>已写入 ✓</h2>
      <p class="dim">
        实体卡 {{ committed.writtenEntities.length }} 张 · 机制卡 {{ committed.cards }} 张 · 边
        {{ committed.edges }} 条
      </p>
      <div class="row">
        <button class="primary" @click="router.push('/graph')">去图谱看结果</button>
        <button @click="router.push('/mechanism')">去知识层看机制卡</button>
        <button @click="backToSearch">返回搜索</button>
      </div>
    </div>

    <template v-else-if="draft">
      <header class="head">
        <h2>审核 · {{ draft.topic }}</h2>
        <div class="chips">
          <span v-for="k in draft.keywords" :key="k" class="chip">{{ k }}</span>
        </div>
        <p v-if="draft.matched" class="dim">
          可信源 {{ draft.sources.length }} 个平台 · 条目 {{ draft.items.length }} 条<span
            v-if="draft.llmRoute"
          >
            · 模型 {{ draft.llmRoute }}</span
          ><span v-if="draft.llmDegraded" class="degraded">
            · ⚠ 已降级（链首不可用，后面的接住了）</span
          >
        </p>
      </header>

      <!-- 没可信源：抽不出实体 -->
      <div v-if="draft.needsConfig" class="empty">
        <div class="empty-icon">⚠</div>
        <h3>没有可信源，无法抽取</h3>
        <p class="dim">先为「{{ draft.topic }}」配置可信源，再回来生成。</p>
        <button class="primary" @click="goSettings">去设置里配置可信源</button>
      </div>

      <!-- 有源但没抽出实体：区分「模型调用失败」与「模型没给」 -->
      <div v-else-if="!draft.entities.length" class="empty">
        <div class="empty-icon">⚠</div>
        <template v-if="draft.llmError">
          <h3>模型调用失败</h3>
          <p class="dim mono err-detail">{{ draft.llmError }}</p>
          <p class="dim">
            可信源已找到，是模型这一跳断了（网关 / 额度 / 模型名）。修好
            <code>LLM_CHAIN_MAIN</code> 里的资源后重试即可。
          </p>
        </template>
        <template v-else>
          <h3>模型没抽出实体</h3>
          <p class="dim">可信源有了，但 L3 没产出实体。可换个更具体的主题，或回设置补充源。</p>
        </template>
      </div>

      <template v-else>
        <section class="block">
          <div class="block-head">
            <h3>
              实体（L3 拓扑）
              <span class="count mono"
                >{{ selectedCount.entities }}/{{ draft.entities.length }}</span
              >
            </h3>
            <div class="toggle">
              <button @click="toggleAll(entityOn, true)">全选</button>
              <button @click="toggleAll(entityOn, false)">全不选</button>
            </div>
          </div>
          <ul class="items">
            <li v-for="(e, i) in draft.entities" :key="e.name" :class="{ off: !entityOn[i] }">
              <label>
                <input v-model="entityOn[i]" type="checkbox" />
                <span class="name">{{ e.name }}</span>
                <span class="type mono">{{ e.type }}</span>
              </label>
              <p v-if="e.oneLine" class="one">{{ e.oneLine }}</p>
            </li>
          </ul>
        </section>

        <section class="block">
          <div class="block-head">
            <h3>
              机制卡（L4 知识层）
              <span class="count mono">{{ selectedCount.cards }}/{{ draft.cards.length }}</span>
            </h3>
            <div class="toggle">
              <button @click="toggleAll(cardOn, true)">全选</button>
              <button @click="toggleAll(cardOn, false)">全不选</button>
            </div>
          </div>
          <p v-if="!draft.cards.length" class="dim">（本次没抽出机制卡）</p>
          <ul v-else class="items">
            <li v-for="(c, i) in draft.cards" :key="c.name" :class="{ off: !cardOn[i] }">
              <label>
                <input v-model="cardOn[i]" type="checkbox" />
                <span class="name">{{ c.name }}</span>
                <span class="type mono">机制卡</span>
              </label>
              <p v-if="c.mechanism" class="one">{{ c.mechanism }}</p>
              <p v-if="c.cases.length" class="cases mono">挂：{{ c.cases.join('、') }}</p>
            </li>
          </ul>
        </section>

        <section class="block">
          <div class="block-head">
            <h3>
              边（L4 图谱）
              <span class="count mono">{{ selectedCount.edges }}/{{ draft.edges.length }}</span>
            </h3>
            <div class="toggle">
              <button @click="toggleAll(edgeOn, true)">全选</button>
              <button @click="toggleAll(edgeOn, false)">全不选</button>
            </div>
          </div>
          <p v-if="!draft.edges.length" class="dim">（本次没判出边）</p>
          <template v-else>
            <div v-if="progressItems.length" class="edge-group">
              <div class="group-label mono">递进（竖·深度）</div>
              <ul class="items">
                <li
                  v-for="it in progressItems"
                  :key="`p${it.index}`"
                  :class="{ off: !edgeOn[it.index] }"
                >
                  <label>
                    <input v-model="edgeOn[it.index]" type="checkbox" />
                    <span class="name">{{ it.edge.src }}</span>
                    <span class="edge mono">{{ it.edge.type }}→</span>
                    <span class="name">{{ it.edge.dst }}</span>
                  </label>
                  <p v-if="it.edge.reason" class="one">{{ it.edge.reason }}</p>
                </li>
              </ul>
            </div>
            <div v-if="applyItems.length" class="edge-group">
              <div class="group-label mono">应用（卡 → 实体）</div>
              <ul class="items">
                <li
                  v-for="it in applyItems"
                  :key="`a${it.index}`"
                  :class="{ off: !edgeOn[it.index] }"
                >
                  <label>
                    <input v-model="edgeOn[it.index]" type="checkbox" />
                    <span class="name">{{ it.edge.src }}</span>
                    <span class="edge mono">{{ it.edge.type }}→</span>
                    <span class="name">{{ it.edge.dst }}</span>
                  </label>
                  <p v-if="it.edge.reason" class="one">{{ it.edge.reason }}</p>
                </li>
              </ul>
            </div>
          </template>
        </section>

        <footer class="foot">
          <span class="dim"
            >写入 git 真相源：data/wiki/ · data/graph/edges.md · data/mechanism/cards.md</span
          >
          <div class="row">
            <button class="primary" :disabled="committing" @click="commit">
              {{
                committing
                  ? '写入中…'
                  : `确认写入（${selectedCount.entities} 实体 · ${selectedCount.cards} 卡 · ${selectedCount.edges} 边）`
              }}
            </button>
            <button :disabled="committing" @click="backToSearch">放弃</button>
          </div>
        </footer>
      </template>
    </template>
  </div>
</template>

<style scoped>
.wrap {
  max-width: 880px;
  padding-bottom: 90px;
}

.head h2 {
  font-family: 'Songti SC', 'Noto Serif SC', serif;
  font-size: 20px;
}

.head .dim {
  margin-top: 6px;
  font-size: 12px;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 10px;
}

.chip {
  padding: 3px 10px;
  font-size: 12px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
}

.block {
  margin-top: 22px;
}

.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.block-head h3 {
  font-size: 13px;
  letter-spacing: 1px;
  color: var(--dim);
}

.count {
  margin-left: 8px;
  font-size: 11px;
  color: var(--flow);
}

.toggle {
  display: flex;
  gap: 6px;
}

.toggle button {
  padding: 3px 9px;
  font-size: 11.5px;
}

.items {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.items li {
  padding: 11px 13px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 10px;
}

.items li.off {
  opacity: 0.45;
}

.items label {
  display: flex;
  gap: 8px;
  align-items: center;
  cursor: pointer;
}

.items input {
  accent-color: var(--flow);
}

.name {
  font-size: 14px;
  font-weight: 600;
}

.type {
  font-size: 10.5px;
  color: var(--dim);
}

.edge {
  padding: 0 4px;
  color: var(--flow);
  font-size: 11px;
}

.one {
  margin-top: 6px;
  font-size: 12.5px;
  color: var(--dim);
  line-height: 1.6;
}

.cases {
  margin-top: 6px;
  font-size: 11px;
  color: #e8b05c;
}

.edge-group {
  margin-top: 8px;
}

.edge-group + .edge-group {
  margin-top: 14px;
}

.group-label {
  margin-bottom: 8px;
  font-size: 11px;
  letter-spacing: 1px;
  color: var(--amber);
}

.empty {
  margin-top: 26px;
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
  margin: 8px 0 6px;
  font-size: 16px;
  color: var(--ink);
}

.empty .dim {
  margin-bottom: 14px;
  font-size: 13px;
  line-height: 1.7;
}

/* 降级提示：不是错误，但必须看得见（x_ai router 的「降级必须可见」） */
.degraded {
  color: #e8b04b;
}

.err-detail {
  padding: 8px 10px;
  text-align: left;
  font-size: 11.5px;
  color: #ffb4b4;
  word-break: break-all;
  background: rgba(229, 83, 75, 0.06);
  border: 1px solid #5a2a2a;
  border-radius: 8px;
}

.done {
  margin-top: 24px;
}

.done h2 {
  font-family: 'Songti SC', 'Noto Serif SC', serif;
  font-size: 20px;
  color: var(--flow);
}

.done .dim {
  margin-top: 8px;
}

.row {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  margin-top: 16px;
}

.foot {
  position: fixed;
  left: 224px;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 20px;
  background: rgba(11, 14, 19, 0.92);
  border-top: 1px solid var(--line);
}

.foot .dim {
  font-size: 11px;
}

button.primary {
  font-weight: 600;
  color: #06282a;
  background: var(--flow);
  border-color: var(--flow);
}

button.primary:disabled {
  opacity: 0.5;
  cursor: default;
}

button:disabled {
  opacity: 0.5;
  cursor: default;
}

.dim {
  color: var(--dim);
}

.err {
  margin-top: 14px;
  padding: 10px 12px;
  border: 1px solid #5a2a2a;
  border-radius: 9px;
  color: #ffb4b4;
  font-size: 12.5px;
}
</style>
