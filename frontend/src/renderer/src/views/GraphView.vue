<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import cytoscape from 'cytoscape'
import type { Core, ElementDefinition, LayoutOptions, NodeSingular } from 'cytoscape'

import { useAtlasStore } from '@/stores/atlas'

const store = useAtlasStore()
const router = useRouter()

const layer = ref<'all' | 'l3' | 'l4'>('all')
const filter = ref<'all' | '递进' | '应用'>('all')
const container = ref<HTMLDivElement>()
let cy: Core | null = null

/** 领域 → 颜色图例（按首个出现顺序） */
const legend = computed(() => {
  const seen = new Map<string, string>()
  for (const n of store.graph?.nodes ?? []) if (!seen.has(n.domain)) seen.set(n.domain, n.color)
  return [...seen.entries()]
})

function coseLayout(): LayoutOptions {
  return {
    name: 'cose',
    animate: false,
    padding: 50,
    nodeRepulsion: 9000,
    idealEdgeLength: 130,
    nodeOverlap: 24,
    gravity: 0.25,
    numIter: 1200
  }
}

function build(): void {
  if (!container.value || !store.graph) return
  cy?.destroy()

  const { nodes, links } = store.graph
  const degree: Record<string, number> = {}
  for (const l of links) {
    degree[l.src] = (degree[l.src] ?? 0) + 1
    degree[l.dst] = (degree[l.dst] ?? 0) + 1
  }

  const elements: ElementDefinition[] = [
    ...nodes.map(n => ({
      data: {
        id: n.key,
        label: n.name,
        color: n.color,
        etype: n.etype,
        oneLine: n.oneLine,
        degree: degree[n.key] ?? 0
      }
    })),
    ...links.map((l, i) => ({
      data: { id: `e${i}`, source: l.src, target: l.dst, type: l.type, reason: l.reason }
    }))
  ]

  cy = cytoscape({
    container: container.value,
    elements,
    minZoom: 0.2,
    maxZoom: 3,
    style: [
      {
        selector: 'node',
        style: {
          shape: 'ellipse',
          // 度 → 节点大小：连接越多点越大（图数据库的直觉）
          width: 'mapData(degree, 0, 8, 26, 70)',
          height: 'mapData(degree, 0, 8, 26, 70)',
          'background-color': 'data(color)',
          'background-opacity': 0.22,
          'border-color': 'data(color)',
          'border-width': 1.6,
          label: 'data(label)',
          color: '#cdd9e5',
          'font-size': 11,
          'text-valign': 'bottom',
          'text-margin-y': 8,
          'text-wrap': 'ellipsis',
          'text-max-width': '96px',
          'text-background-color': '#0b0e13',
          'text-background-opacity': 0.7,
          'text-background-padding': '3px'
        }
      },
      // 机制卡 = 金线：双环 + 加粗描边
      {
        selector: 'node[etype = "机制卡"]',
        style: { 'border-width': 2.6, 'border-style': 'double' }
      },
      {
        selector: 'edge',
        style: {
          width: 1.6,
          'curve-style': 'bezier',
          'line-color': '#4fd1c5',
          'target-arrow-color': '#4fd1c5',
          'target-arrow-shape': 'triangle',
          'arrow-scale': 1,
          opacity: 0.7
        }
      },
      // 应用边 = 锚点：琥珀虚线
      {
        selector: 'edge[type = "应用"]',
        style: { 'line-color': '#e8a33d', 'target-arrow-color': '#e8a33d', 'line-style': 'dashed' }
      },
      { selector: '.dimmed', style: { opacity: 0.18 } }
    ],
    layout: coseLayout()
  })

  // 点击跳转：实体 → 卡片页；机制卡 → 机制卡页
  cy.on('tap', 'node', evt => {
    const n = evt.target as NodeSingular
    void router.push(n.data('etype') === '机制卡' ? '/mechanism' : `/cards/${n.id()}`)
  })

  // 悬停高亮：邻居 + 相连边保持，其余变淡
  cy.on('mouseover', 'node', evt => {
    cy?.elements().difference((evt.target as NodeSingular).closedNeighborhood()).addClass('dimmed')
  })
  cy.on('mouseout', 'node', () => cy?.elements().removeClass('dimmed'))
}

/** 层过滤（L3 图谱层 = 实体 + 递进边；L4 知识层 = 机制卡 + 应用边）叠加边类型过滤 */
function applyFilter(): void {
  if (!cy) return
  const showCards = layer.value !== 'l3'
  const showEntities = layer.value !== 'l4'
  cy.nodes().forEach(n => {
    const isCard = n.data('etype') === '机制卡'
    n.style('display', (isCard ? showCards : showEntities) ? 'element' : 'none')
  })
  cy.edges().forEach(e => {
    const isApply = e.data('type') === '应用'
    const byType = filter.value === 'all' || e.data('type') === filter.value
    e.style('display', byType && (isApply ? showCards : showEntities) ? 'element' : 'none')
  })
}

watch([filter, layer], () => {
  applyFilter()
  cy?.layout(coseLayout()).run() // 隐藏的节点退出布局范围，重排一次
})
onMounted(build)
onBeforeUnmount(() => cy?.destroy())
</script>

<template>
  <div class="wrap">
    <div class="bar">
      <span class="lbl mono">层</span>
      <button :class="{ on: layer === 'all' }" @click="layer = 'all'">全部</button>
      <button :class="{ on: layer === 'l3' }" @click="layer = 'l3'">L3 图谱层</button>
      <button :class="{ on: layer === 'l4' }" @click="layer = 'l4'">L4 知识层</button>
      <span class="lbl mono">边</span>
      <button :class="{ on: filter === 'all' }" @click="filter = 'all'">全部</button>
      <button :class="{ on: filter === '递进' }" @click="filter = '递进'">递进</button>
      <button :class="{ on: filter === '应用' }" @click="filter = '应用'">应用</button>
      <span class="mono dim">
        {{ store.graph?.nodes.length ?? 0 }} 节点 · {{ store.graph?.links.length ?? 0 }} 边
      </span>
    </div>

    <div class="legend">
      <span v-for="[d, c] in legend" :key="d" class="lg"><i :style="{ background: c }" />{{ d }}</span>
      <span class="lg hint">◇ 双环 = 机制卡（金线）</span>
    </div>

    <div v-if="store.graph?.dangling.length" class="dangling mono">
      ⚠ {{ store.graph.dangling.length }} 条边的端点尚未建卡：
      <span v-for="d in store.graph.dangling" :key="d" class="chip">{{ d }}</span>
    </div>

    <div ref="container" class="stage" />
  </div>
</template>

<style scoped>
.wrap {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.bar {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  align-items: center;
}

.bar .dim {
  color: var(--dim);
  font-size: 12px;
}

.bar .lbl {
  color: var(--dim);
  font-size: 11px;
  letter-spacing: 1px;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 10px;
}

.lg {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  font-size: 11.5px;
  color: var(--dim);
}

.lg i {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.lg.hint {
  color: #e8b05c;
}

.dangling {
  margin-top: 10px;
  font-size: 11.5px;
  color: var(--amber);
}

.chip {
  display: inline-block;
  margin: 4px 6px 0 0;
  padding: 3px 8px;
  border: 1px dashed #4a3b1f;
  border-radius: 8px;
  color: #c9b48a;
}

.stage {
  flex: 1;
  min-height: 0;
  margin-top: 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background:
    radial-gradient(circle at 1px 1px, rgba(255, 255, 255, 0.04) 1px, transparent 0) 0 0 / 26px 26px;
}
</style>
