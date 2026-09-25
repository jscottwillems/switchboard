<script setup lang="ts">
import { formatOffset } from '@/lib/format'
import { speakerLabel, transcriptSourceLabel } from '@/lib/labels'
import type { TranscriptSegment } from '@/types/models'

defineProps<{ turns: TranscriptSegment[] }>()
</script>

<template>
  <div>
    <p class="caption">
      Segments are observations. <span class="mono">stt_confidence</span> is the recognizer score, not Switchboard confidence.
    </p>
    <ol v-if="turns.length" class="transcript">
      <li v-for="turn in turns" :key="turn.id" :data-speaker="turn.speaker">
        <span class="t-time">{{ formatOffset(turn.start_offset_ms) }}</span>
        <span class="t-who">{{ speakerLabel(turn.speaker) }}</span>
        <span class="t-text">
          {{ turn.text }}
          <span class="kind">{{ transcriptSourceLabel(turn.source) }}</span>
        </span>
      </li>
    </ol>
    <p v-else class="empty">No transcript segments in this snapshot.</p>
  </div>
</template>
