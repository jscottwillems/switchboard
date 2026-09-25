<script setup lang="ts">
import ProvenanceBadge from '@/components/ProvenanceBadge.vue'
import { findingKindLabel } from '@/lib/labels'
import type { FindingRow } from '@/types/models'

defineProps<{ items: FindingRow[] }>()
</script>

<template>
  <ul v-if="items.length" class="chips">
    <li v-for="item in items" :key="item.id">
      <ProvenanceBadge :layer="item.record_layer" />
      <span>{{ findingKindLabel(item.kind) }}: {{ item.raw_quote }}</span>
    </li>
  </ul>
  <span v-else class="muted">None</span>
</template>
