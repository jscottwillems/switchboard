<script setup lang="ts">
import ProvenanceBadge from '@/components/ProvenanceBadge.vue'
import { conversationStateLabel } from '@/lib/labels'
import type { ConversationState, Provenance } from '@/types/models'

defineProps<{
  state: ConversationState
  provenance?: Provenance
}>()
</script>

<template>
  <span class="state-tag" :data-state="state">
    <span>{{ conversationStateLabel(state) }}</span>
    <ProvenanceBadge v-if="provenance" :provenance="provenance" />
  </span>
</template>
