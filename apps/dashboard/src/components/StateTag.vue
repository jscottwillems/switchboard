<script setup lang="ts">
import ProvenanceBadge from '@/components/ProvenanceBadge.vue'
import { conversationStateLabel } from '@/lib/labels'
import type { ConversationState, RecordLayer } from '@/types/models'

defineProps<{
  state: ConversationState
  layer?: RecordLayer
}>()
</script>

<template>
  <span class="state-tag" :data-state="state">
    <span>{{ conversationStateLabel(state) }}</span>
    <ProvenanceBadge v-if="layer" :layer="layer" />
  </span>
</template>
