<script setup lang="ts">
import { activityDays, countFor, maxActivityCount } from '@/lib/activity'
import { formatDay } from '@/lib/format'
import type { ActivityBucket } from '@/types/models'
import { computed } from 'vue'

const props = defineProps<{ activity: ActivityBucket[] }>()

const hours = Array.from({ length: 24 }, (_, hour) => hour)
const days = computed(() => activityDays(props.activity))
const maxCount = computed(() => maxActivityCount(props.activity))
const summary = computed(() => {
  const total = props.activity.reduce((sum, bucket) => sum + bucket.count, 0)
  return `Hourly call volume, ${total} calls across ${days.value.length} days, UTC`
})

function level(day: string, hour: number): number {
  if (maxCount.value === 0) return 0
  return countFor(props.activity, day, hour) / maxCount.value
}

function count(day: string, hour: number): number {
  return countFor(props.activity, day, hour)
}
</script>

<template>
  <div v-if="days.length" class="heatmap-wrap">
    <div class="heatmap" role="img" :aria-label="summary" :style="{ gridTemplateColumns: `72px repeat(24, 16px)` }">
      <span />
      <span v-for="hour in hours" :key="hour" class="heat-hour">{{ hour % 3 === 0 ? hour : '' }}</span>
      <template v-for="day in days" :key="day">
        <span class="heat-day">{{ formatDay(day) }}</span>
        <span
          v-for="hour in hours"
          :key="`${day}-${hour}`"
          class="heat-cell"
          :style="{ '--level': level(day, hour) }"
          :title="`${day} ${String(hour).padStart(2, '0')}:00 UTC · ${count(day, hour)} calls`"
          aria-hidden="true"
        />
      </template>
    </div>
    <p class="caption">Hours are UTC. Darker cells are higher answered-call volume. Zero cells stay empty.</p>
  </div>
  <p v-else class="empty">No hourly activity in this campaign.</p>
</template>
