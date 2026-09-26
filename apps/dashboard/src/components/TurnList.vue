<script setup lang="ts">
import ProvenanceBadge from '@/components/ProvenanceBadge.vue'
import { formatPercent } from '@/lib/format'
import { speakerLabel } from '@/lib/labels'
import type { ConversationTurn } from '@/types/models'

defineProps<{ turns: ConversationTurn[] }>()
</script>

<template>
  <div>
    <p class="caption">
      Turns are interpretations. Each one cites transcript segment ids and carries its own confidence.
    </p>
    <ol v-if="turns.length" class="transcript">
      <li v-for="turn in turns" :key="turn.id" :data-speaker="turn.speaker">
        <span class="t-time">{{ turn.turn_index }}</span>
        <span class="t-who">{{ speakerLabel(turn.speaker) }}</span>
        <span class="t-text">
          {{ turn.text }}
          <ProvenanceBadge layer="interpretation" />
          <span v-if="turn.strategy_id" class="kind">{{ turn.strategy_id }}</span>
          <span class="conf">{{ formatPercent(turn.confidence) }}</span>
        </span>
      </li>
    </ol>
    <p v-else class="empty">No conversation turns for this call.</p>
  </div>
</template>
