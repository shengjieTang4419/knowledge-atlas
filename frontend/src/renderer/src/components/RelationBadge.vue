<script setup lang="ts">
import type { RelationType } from '../../../shared/ipc'

/** 关系徽章：递进 = 青（is-a/contains）；应用 = 琥珀（applies-to，卡→实体） */
defineProps<{ type: RelationType }>()
</script>

<template>
  <span class="badge" :class="type === '应用' ? 'apply' : 'prereq'">{{ type }}</span>
</template>

<style scoped>
.badge {
  display: inline-block;
  margin-right: 5px;
  padding: 1px 7px;
  border-radius: 8px;
  font-size: 10.5px;
  font-weight: 700;
}

.prereq {
  color: #06282a;
  background: var(--flow);
}

.apply {
  color: #2a1a05;
  background: var(--amber);
}
</style>
