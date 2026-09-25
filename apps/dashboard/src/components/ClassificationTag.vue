<script setup lang="ts">
import ProvenanceBadge from '@/components/ProvenanceBadge.vue'
import { formatPercent } from '@/lib/format'
import { classificationLabel } from '@/lib/labels'
import type { ClassifiedValue } from '@/types/models'

defineProps<{ classification: ClassifiedValue }>()
</script>

<template>
  <span class="class-tag">
    <span>{{ classificationLabel(classification.label) }}</span>
    <ProvenanceBadge :layer="classification.record_layer" />
    <span v-if="classification.confidence !== null" class="conf">{{ formatPercent(classification.confidence) }}</span>
  </span>
</template>
