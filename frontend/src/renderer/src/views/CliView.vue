<script setup lang="ts">
import { ref } from 'vue'

import type { CliResult } from '../../../shared/ipc'
import { api } from '@/api'

/** 逐层对应 CLI 子命令（按设计文档分层命名）；参数允许自由追加 */
const LAYERS = [
  { cmd: 'orient', label: 'L1 Topic 层 · 拆词', args: ['Java 多线程 · 内存可见性'] },
  { cmd: 'sources', label: 'L2 检索层 · 可信源', args: ['Java 多线程 · 内存可见性'] },
  { cmd: 'topology', label: 'L3 图谱层 · 拓扑', args: ['Java 多线程 · 内存可见性'] },
  {
    cmd: 'attach',
    label: 'L4 知识层 · 挂载（dry-run）',
    args: ['Java 多线程 · 内存可见性', '--dry-run']
  },
  { cmd: 'cards', label: 'L4 · 机制卡列表', args: ['--json'] },
  { cmd: 'profile', label: '横切 · Profile（画像）', args: [] }
]

const picked = ref(LAYERS[0].cmd)
const extra = ref('')
const result = ref<CliResult | null>(null)
const running = ref(false)

function argsOf(cmd: string): string[] {
  const layer = LAYERS.find(l => l.cmd === cmd)
  const base = layer ? [...layer.args] : []
  const tail = extra.value.trim()
  return tail ? [...base, ...tail.split(/\s+/)] : base
}

async function run(): Promise<void> {
  running.value = true
  result.value = null
  try {
    result.value = await api.cliRun([picked.value, ...argsOf(picked.value)])
  } finally {
    running.value = false
  }
}
</script>

<template>
  <div>
    <div class="bar">
      <select v-model="picked">
        <option v-for="l in LAYERS" :key="l.cmd" :value="l.cmd">{{ l.label }}</option>
      </select>
      <input v-model="extra" placeholder="追加参数（可空）" />
      <button :disabled="running" @click="run">{{ running ? '跑…' : '执行' }}</button>
    </div>

    <p class="note mono">
      <b>逐层跑一遍看真实产出</b>（学习/调试用）：命令在仓库根执行
      <code>uv run python -m app.cli …</code>，业务全在 Python，壳只转发。
    </p>

    <template v-if="result">
      <p class="mono status" :class="{ bad: !result.ok }">
        {{ result.ok ? '✓' : '✗' }} {{ result.command }}
      </p>
      <pre v-if="result.stdout" class="out">{{ result.stdout }}</pre>
      <pre v-if="result.stderr" class="out err">{{ result.stderr }}</pre>
    </template>
  </div>
</template>

<style scoped>
.bar {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  align-items: center;
}

select,
input {
  padding: 7px 11px;
  color: var(--ink);
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  font-family: inherit;
  font-size: 13px;
}

select:focus,
input:focus {
  outline: none;
  border-color: var(--flow);
}

button:disabled {
  opacity: 0.5;
  cursor: default;
}

.note {
  margin-top: 12px;
  font-size: 11.5px;
  color: var(--dim);
}

.status {
  margin-top: 14px;
  font-size: 12px;
  color: var(--flow);
}

.status.bad {
  color: #ff8f8f;
}

.out {
  margin-top: 8px;
  padding: 13px 15px;
  font-family: ui-monospace, Menlo, monospace;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 10px;
}

.out.err {
  border-color: #5a2a2a;
  color: #ffb4b4;
}
</style>
