<script setup lang="ts">
import { formatTimestamp } from '@/lib/format'

const props = defineProps<{
  sttMs: number
  llmMs: number
  ttsMs: number
  e2eMs: number
  sampledAt?: string
}>()

const budgets = {
  sttMs: 800,
  llmMs: 1200,
  ttsMs: 700,
  e2eMs: 2500,
} as const

type MeterKey = keyof typeof budgets

const meters: Array<{ key: MeterKey; label: string }> = [
  { key: 'sttMs', label: 'STT' },
  { key: 'llmMs', label: 'LLM' },
  { key: 'ttsMs', label: 'TTS' },
  { key: 'e2eMs', label: 'E2E' },
]

function valueFor(key: MeterKey): number {
  switch (key) {
    case 'sttMs':
      return props.sttMs
    case 'llmMs':
      return props.llmMs
    case 'ttsMs':
      return props.ttsMs
    case 'e2eMs':
      return props.e2eMs
    default: {
      const unexpected: never = key
      return unexpected
    }
  }
}

function fraction(key: MeterKey): number {
  return Math.min(1, valueFor(key) / budgets[key])
}

function overBudget(key: MeterKey): boolean {
  return valueFor(key) > budgets[key]
}
</script>

<template>
  <div class="latency">
    <div class="latency-head">
      <h2>Pipeline latency</h2>
      <p v-if="sampledAt" class="caption">Sampled {{ formatTimestamp(sampledAt) }}</p>
    </div>
    <div class="latency-grid">
      <div v-for="meter in meters" :key="meter.key" class="latency-cell">
        <div class="latency-label">
          <span>{{ meter.label }}</span>
          <strong :data-over="overBudget(meter.key)">{{ valueFor(meter.key) }} ms</strong>
        </div>
        <div class="meter" :data-over="overBudget(meter.key)">
          <span :style="{ width: `${fraction(meter.key) * 100}%` }" />
        </div>
      </div>
    </div>
    <p class="caption">Bars scale to a display budget (STT 800 / LLM 1200 / TTS 700 / E2E 2500 ms). E2E is latest-turn time to first audio.</p>
  </div>
</template>
