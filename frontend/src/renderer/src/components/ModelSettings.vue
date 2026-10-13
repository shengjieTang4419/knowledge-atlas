<script setup lang="ts">
/**
 * 模型配置面板：provider（家）+ 链路（档位 → 有序候选）+ MoA 模式。
 *
 * 配置落 `data/settings/llm.json`（不入 git）；`.env` 只做播种。
 * 明文 Key 只写不读——读接口不回传，所以「留空 = 不改」，要换就重填。
 */
import { computed, onMounted, ref } from 'vue'

import type { LlmConfigView, LlmProbeItem } from '../../../shared/ipc'
import { api } from '@/api'

const cfg = ref<LlmConfigView | null>(null)
/** 探针结论按 `档位 → provider/model` 存：结论认的是**候选身份**，不是行号（见 rows 注释）。 */
const probe = ref<Record<string, Record<string, LlmProbeItem>>>({})
const error = ref('')
const notice = ref('')
const busy = ref(false)
const probing = ref(false)
/** 已保存配置的快照，用来判断界面上有没有未保存改动。 */
const savedSnapshot = ref('')

const TIERS: { id: string; label: string }[] = [
  { id: 'main', label: '主力（抽取/判边）' },
  { id: 'cheap', label: '轻任务（拆词）' }
]

/** 链里用到的 provider id（用于「链项」下拉与校验） */
const providerIds = computed(() => (cfg.value?.providers ?? []).map(p => p.id))

function fail(e: unknown): void {
  error.value = e instanceof Error ? e.message : String(e)
}

function entryModel(entry: string): string {
  const i = entry.indexOf('/')
  return i >= 0 ? entry.slice(i + 1) : entry
}

function entryProvider(entry: string, defaultId: string): string {
  const i = entry.indexOf('/')
  return i >= 0 ? entry.slice(0, i) : defaultId
}

/** 链项拼装：默认家写裸模型名（跟着默认家走），别家写 `<provider>/<model>` */
function makeEntry(provider: string, model: string): string {
  const m = model.trim()
  if (!m) return ''
  return !provider || provider === cfg.value?.defaultProvider ? m : `${provider}/${m}`
}

/** 链项身份：一律写成 `provider/model`，与探针结果的口径一致（裸名字按默认家补全）。 */
function candidateKey(entry: string): string {
  const model = entryModel(entry).trim()
  if (!model) return ''
  return `${entryProvider(entry, cfg.value?.defaultProvider ?? '')}/${model}`
}

/** 链上一行 = 当前条目 + 该条目自己的探针结论。 */
interface ChainRow {
  entry: string
  probeText: string
  probeOk: boolean
}

/**
 * 结论**按身份**挂到行上，不按行号。
 *
 * 按行号挂的后果实测踩过：把第 1 行从 `gpt-plus` 改成 `deepseek-flash` 后，
 * 上一次探针的 `❌ ifans/gpt-plus: HTTP 500` 还留在第 1 行底下——文字里写着旧模型名，
 * 看上去像「改了没生效」。身份不匹配就不显示，改行/删行/换序都自动失效。
 */
const rows = computed<Record<string, ChainRow[]>>(() => {
  const out: Record<string, ChainRow[]> = {}
  for (const t of TIERS) {
    out[t.id] = (cfg.value?.chains[t.id]?.entries ?? []).map(entry => {
      const key = candidateKey(entry)
      const hit = key ? probe.value[t.id]?.[key] : undefined
      return {
        entry,
        probeText: hit ? (hit.ok ? `✅ ${hit.ms}ms` : `❌ ${hit.error}`) : '',
        probeOk: hit?.ok ?? false
      }
    })
  }
  return out
})

/** 界面上有未保存改动：此时「测试连通」跑的是**已保存**的配置，不是屏幕上这条链。 */
const dirty = computed(() => !!cfg.value && JSON.stringify(cfg.value) !== savedSnapshot.value)

async function refresh(): Promise<void> {
  try {
    cfg.value = await api.llmConfig()
    savedSnapshot.value = JSON.stringify(cfg.value)
  } catch (e) {
    fail(e)
  }
}

async function save(): Promise<void> {
  if (!cfg.value || busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    cfg.value = await api.llmConfigSave(cfg.value)
    savedSnapshot.value = JSON.stringify(cfg.value)
    notice.value = '已保存（下一次调用即生效，无需重启）'
  } catch (e) {
    fail(e)
  } finally {
    busy.value = false
  }
}

async function testChain(): Promise<void> {
  if (probing.value || dirty.value) return
  probing.value = true
  error.value = ''
  notice.value = ''
  try {
    const tiers = await api.llmProbe('all')
    const verdicts: Record<string, Record<string, LlmProbeItem>> = {}
    for (const t of tiers) {
      verdicts[t.tier] = Object.fromEntries(t.results.map(r => [`${r.provider}/${r.model}`, r]))
    }
    probe.value = verdicts
    const flat = tiers.flatMap(t => t.results)
    const ok = flat.filter(r => r.ok).length
    notice.value = flat.length
      ? `测试完成：${ok}/${flat.length} 个候选可用`
      : '链上没有可测的候选（检查 provider 与 Key）'
  } catch (e) {
    fail(e)
  } finally {
    probing.value = false
  }
}

/** 改 provider 标识时，把引用它的地方一起改。
 *
 * 不跟的话：链路里 `relay/deepseek-chat` 会指向一个不存在的家 → 该候选**静默消失**，
 * 用户只会看到「模型没抽出实体」，与上次那次 503 事故属同一类误诊。改名是常见操作，不能变暗雷。
 */
function renameProvider(index: number, next: string): void {
  if (!cfg.value) return
  const provider = cfg.value.providers[index]
  const prev = provider.id
  if (prev === next) return
  provider.id = next
  if (cfg.value.defaultProvider === prev) cfg.value.defaultProvider = next
  for (const chain of Object.values(cfg.value.chains)) {
    chain.entries = chain.entries.map(e => {
      const i = e.indexOf('/')
      if (i < 0) return e // 裸模型名跟着「默认家」走，不需要改
      return e.slice(0, i) === prev ? `${next}${e.slice(i)}` : e
    })
  }
  notice.value = `已把引用 ${prev} 的链路项一起改名为 ${next}`
}

function addProvider(): void {
  if (!cfg.value) return
  const id = `p${cfg.value.providers.length + 1}`
  cfg.value.providers.push({
    id,
    baseUrl: '',
    apiKey: '',
    apiKeyEnv: '',
    hasKey: false,
    keyHint: '未填 Key'
  })
}

function removeProvider(id: string): void {
  if (!cfg.value) return
  cfg.value.providers = cfg.value.providers.filter(p => p.id !== id)
  for (const chain of Object.values(cfg.value.chains)) {
    chain.entries = chain.entries.filter(e => entryProvider(e, cfg.value!.defaultProvider) !== id)
  }
}

function addEntry(tier: string): void {
  const chain = cfg.value?.chains[tier]
  if (chain) chain.entries.push('')
}

function removeEntry(tier: string, index: number): void {
  cfg.value?.chains[tier].entries.splice(index, 1)
}

function moveEntry(tier: string, index: number, delta: number): void {
  const entries = cfg.value?.chains[tier].entries
  if (!entries) return
  const to = index + delta
  if (to < 0 || to >= entries.length) return
  const [item] = entries.splice(index, 1)
  entries.splice(to, 0, item)
}

function setEntry(tier: string, index: number, provider: string, model: string): void {
  const entries = cfg.value?.chains[tier].entries
  if (entries) entries[index] = makeEntry(provider, model)
}

onMounted(refresh)
</script>

<template>
  <div v-if="cfg" class="wrap">
    <p v-if="error" class="msg err mono">{{ error }}</p>
    <p v-if="notice" class="msg ok mono">{{ notice }}</p>

    <p class="lead">
      一家模型坏了不该断掉整条链路：下面的<strong>链</strong>按顺序试，第一个答上来的就用它。
      <span class="mono">MoA</span> 模式则是<strong>都问一遍再融合</strong>（多花 N
      倍调用换一致性）。
    </p>
    <p class="dim src">
      来源：{{ cfg.source === 'env' ? '按 .env 播种（还没在界面存过）' : '界面配置（llm.json）' }} ·
      <span class="mono">{{ cfg.path }}</span>
    </p>

    <!-- ---------- Provider ---------- -->
    <section class="block">
      <div class="block-head">
        <h3>Provider（模型提供方）</h3>
        <button @click="addProvider">+ 加一家</button>
      </div>

      <div v-for="p in cfg.providers" :key="p.id" class="provider">
        <div class="row">
          <label>标识</label>
          <input
            :value="p.id"
            class="w-sm mono"
            placeholder="如 ifans"
            @change="
              renameProvider(
                cfg.providers.indexOf(p),
                ($event.target as HTMLInputElement).value.trim()
              )
            "
          />
          <label>Base URL</label>
          <input v-model="p.baseUrl" class="grow mono" placeholder="https://…/v1" />
          <button class="mini danger" @click="removeProvider(p.id)">删除</button>
        </div>
        <div class="row">
          <label>Key</label>
          <input
            v-model="p.apiKey"
            class="w-md"
            type="password"
            :placeholder="p.hasKey ? '留空 = 不改（已配置）' : '粘贴 API Key'"
          />
          <label>或读环境变量</label>
          <input v-model="p.apiKeyEnv" class="w-md mono" placeholder="LLM_API_KEY" />
        </div>
        <p class="hint mono">
          {{ p.keyHint }}
          <span v-if="p.id === cfg.defaultProvider" class="tag">默认家</span>
        </p>
      </div>
      <p v-if="!cfg.providers.length" class="dim">还没有 provider —— 点「+ 加一家」。</p>

      <div class="row nums">
        <label>默认家</label>
        <select v-model="cfg.defaultProvider">
          <option v-for="id in providerIds" :key="id" :value="id">{{ id }}</option>
        </select>
        <label>单次超时(s)</label>
        <input v-model.number="cfg.timeout" class="w-xs mono" type="number" min="1" />
        <label>最多试几个</label>
        <input v-model.number="cfg.maxAttempts" class="w-xs mono" type="number" min="1" />
      </div>
    </section>

    <!-- ---------- 链路 ---------- -->
    <section v-for="t in TIERS" :key="t.id" class="block">
      <div class="block-head">
        <h3>{{ t.label }}</h3>
        <div class="mode">
          <button
            :class="{ on: cfg.chains[t.id]?.mode !== 'moa' }"
            @click="cfg.chains[t.id] && (cfg.chains[t.id].mode = 'fallback')"
          >
            降级链
          </button>
          <button
            :class="{ on: cfg.chains[t.id]?.mode === 'moa' }"
            @click="cfg.chains[t.id] && (cfg.chains[t.id].mode = 'moa')"
          >
            MoA 融合
          </button>
        </div>
      </div>

      <p class="dim mode-hint">
        {{
          cfg.chains[t.id]?.mode === 'moa'
            ? '链上每个候选都问一遍，列表取并集、标量取多数票（平票取链序靠前）。'
            : '逐个试，第一个给出可用 JSON 的就用它；失败自动换下一家。'
        }}
      </p>

      <ol class="chain">
        <li v-for="(row, i) in rows[t.id] ?? []" :key="i">
          <span class="idx mono">{{ i + 1 }}</span>
          <select
            :value="entryProvider(row.entry, cfg.defaultProvider)"
            @change="
              setEntry(t.id, i, ($event.target as HTMLSelectElement).value, entryModel(row.entry))
            "
          >
            <option v-for="id in providerIds" :key="id" :value="id">{{ id }}</option>
          </select>
          <input
            :value="entryModel(row.entry)"
            class="grow mono"
            placeholder="模型名，如 gpt-plus"
            @input="
              setEntry(
                t.id,
                i,
                entryProvider(row.entry, cfg.defaultProvider),
                ($event.target as HTMLInputElement).value
              )
            "
          />
          <button class="mini" :disabled="i === 0" @click="moveEntry(t.id, i, -1)">↑</button>
          <button
            class="mini"
            :disabled="i === (rows[t.id]?.length ?? 1) - 1"
            @click="moveEntry(t.id, i, 1)"
          >
            ↓
          </button>
          <button class="mini danger" @click="removeEntry(t.id, i)">删除</button>

          <div v-if="row.probeText" class="probe mono" :class="{ ok: row.probeOk }">
            {{ row.probeText }}
          </div>
        </li>
      </ol>
      <button class="mini" @click="addEntry(t.id)">+ 加一个候选</button>
    </section>

    <div class="actions">
      <button class="primary" :disabled="busy" @click="save">保存配置</button>
      <button :disabled="probing || dirty" @click="testChain">
        {{ probing ? '测试中…（逐个真调）' : '测试连通' }}
      </button>
      <span class="dim tip">测试是**真调**：网关上「在模型清单里」≠「调得通」，只有真调算数。</span>
      <span v-if="dirty" class="dim tip warn">
        有未保存改动 —— 测试跑的是已保存的配置，先点「保存配置」
      </span>
    </div>
  </div>
  <p v-else class="dim">读取中…</p>
</template>

<style scoped>
.wrap {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.lead,
.src {
  font-size: 12.5px;
  line-height: 1.75;
  color: var(--dim);
}

.lead strong {
  color: var(--ink);
}

.msg {
  padding: 8px 11px;
  font-size: 12px;
  border-radius: 8px;
}

.err {
  color: #ffb4b4;
  border: 1px solid #5a2a2a;
}

.ok {
  color: var(--flow);
  border: 1px solid rgba(79, 209, 197, 0.4);
}

.block {
  padding: 12px 14px 14px;
  border: 1px solid var(--line);
  border-radius: 11px;
}

.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.block-head h3 {
  font-size: 13.5px;
}

.provider {
  margin-top: 10px;
  padding: 10px 11px;
  background: #0f1620;
  border-radius: 9px;
}

.row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 8px;
}

.row:first-child {
  margin-top: 0;
}

.row label {
  font-size: 11px;
  color: var(--dim);
}

input,
select {
  padding: 6px 9px;
  font-family: inherit;
  font-size: 12px;
  color: var(--ink);
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 7px;
}

input:focus,
select:focus {
  outline: none;
  border-color: var(--flow);
}

.grow {
  flex: 1;
  min-width: 120px;
}

.w-sm {
  width: 92px;
}

.w-md {
  width: 210px;
}

.w-xs {
  width: 62px;
}

.hint {
  margin-top: 6px;
  font-size: 11px;
  color: var(--dim);
}

.tag {
  margin-left: 6px;
  padding: 1px 6px;
  font-size: 10px;
  color: #0b0e13;
  background: var(--flow);
  border-radius: 7px;
}

.mode {
  display: flex;
  gap: 6px;
}

.mode button.on {
  background: rgba(79, 209, 197, 0.12);
  border-color: rgba(79, 209, 197, 0.45);
  color: var(--flow);
}

.mode-hint {
  margin-top: 7px;
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--dim);
}

.chain {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 10px 0;
  list-style: none;
}

.chain li {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  align-items: center;
}

.idx {
  width: 16px;
  font-size: 11px;
  color: var(--dim);
}

.chain select {
  width: 104px;
}

.probe {
  width: 100%;
  font-size: 11px;
  color: #ffb4b4;
}

.probe.ok {
  color: var(--flow);
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  align-items: center;
}

button.primary {
  font-weight: 600;
  color: #06282a;
  background: var(--flow);
  border-color: var(--flow);
}

button.primary:disabled {
  opacity: 0.45;
}

.tip {
  font-size: 11px;
}

.tip.warn {
  color: #ffd28a;
}
</style>
