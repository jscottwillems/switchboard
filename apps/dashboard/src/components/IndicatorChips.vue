<script setup lang="ts">
import BasisMark from '@/components/BasisMark.vue'
import ProvenanceBadge from '@/components/ProvenanceBadge.vue'
import type { IntelligenceItem } from '@/types/models'

defineProps<{ items: IntelligenceItem[] }>()
</script>

<template>
  <ul v-if="items.length" class="chips">
    <li v-for="item in items" :key="item.id">
      <ProvenanceBadge :provenance="item.provenance" />
      <BasisMark :basis="item.basis" />
      <span>{{ item.label }}</span>
    </li>
  </ul>
  <span v-else class="muted">None</span>
</template>
