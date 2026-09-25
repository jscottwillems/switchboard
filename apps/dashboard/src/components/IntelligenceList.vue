<script setup lang="ts">
import ProvenanceBadge from '@/components/ProvenanceBadge.vue'
import { formatPercent } from '@/lib/format'
import { findingKindLabel, findingStatusLabel } from '@/lib/labels'
import type { FindingRow } from '@/types/models'

defineProps<{
  items: FindingRow[]
  empty: string
}>()
</script>

<template>
  <ul v-if="items.length" class="intel-list">
    <li v-for="item in items" :key="item.id" class="intel-row" :data-prov="item.record_layer">
      <div class="intel-top">
        <span class="intel-kind">{{ findingKindLabel(item.kind) }}</span>
        <ProvenanceBadge :layer="item.record_layer" />
        <span class="finding-status" :data-status="item.status">{{ findingStatusLabel(item.status) }}</span>
        <span v-if="item.confidence !== null" class="conf">{{ formatPercent(item.confidence) }}</span>
      </div>
      <p class="intel-label">{{ item.raw_quote }}</p>
      <p class="intel-value">{{ item.value }}</p>
    </li>
  </ul>
  <p v-else class="empty">{{ empty }}</p>
</template>
