<script setup lang="ts">
import BasisMark from '@/components/BasisMark.vue'
import ProvenanceBadge from '@/components/ProvenanceBadge.vue'
import { formatPercent } from '@/lib/format'
import { intelligenceKindLabel } from '@/lib/labels'
import type { IntelligenceItem } from '@/types/models'

defineProps<{
  items: IntelligenceItem[]
  empty: string
}>()
</script>

<template>
  <ul v-if="items.length" class="intel-list">
    <li v-for="item in items" :key="item.id" class="intel-row" :data-prov="item.provenance">
      <div class="intel-top">
        <span class="intel-kind">{{ intelligenceKindLabel(item.kind) }}</span>
        <ProvenanceBadge :provenance="item.provenance" />
        <BasisMark :basis="item.basis" />
        <span v-if="item.confidence !== null" class="conf">{{ formatPercent(item.confidence) }}</span>
      </div>
      <p class="intel-label">{{ item.label }}</p>
      <p class="intel-value">{{ item.value }}</p>
    </li>
  </ul>
  <p v-else class="empty">{{ empty }}</p>
</template>
