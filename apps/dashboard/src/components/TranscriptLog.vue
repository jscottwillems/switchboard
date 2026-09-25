<script setup lang="ts">
import ProvenanceBadge from '@/components/ProvenanceBadge.vue'
import { formatOffset } from '@/lib/format'
import { speakerLabel } from '@/lib/labels'
import type { TranscriptTurn } from '@/types/models'

defineProps<{ turns: TranscriptTurn[] }>()
</script>

<template>
  <div>
    <p class="caption">Unbadged turns are observed speech. A badge means the turn was not committed as observed.</p>
    <ol v-if="turns.length" class="transcript">
      <li v-for="turn in turns" :key="turn.id" :data-speaker="turn.speaker">
        <span class="t-time">{{ formatOffset(turn.offsetMs) }}</span>
        <span class="t-who">{{ speakerLabel(turn.speaker) }}</span>
        <span class="t-text">
          {{ turn.text }}
          <ProvenanceBadge v-if="turn.provenance !== 'observed'" :provenance="turn.provenance" />
        </span>
      </li>
    </ol>
    <p v-else class="empty">No transcript turns in this snapshot.</p>
  </div>
</template>
