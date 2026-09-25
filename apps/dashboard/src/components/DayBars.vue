<script setup lang="ts">
import { rollupByDay } from '@/lib/activity'
import { formatDay } from '@/lib/format'
import type { ActivityBucket } from '@/types/models'
import { computed } from 'vue'

const props = defineProps<{ activity: ActivityBucket[] }>()

const days = computed(() => rollupByDay(props.activity))
const maxCount = computed(() => days.value.reduce((max, day) => Math.max(max, day.count), 0))

function height(count: number): string {
  if (maxCount.value === 0) return '0%'
  return `${Math.max(8, (count / maxCount.value) * 100)}%`
}
</script>

<template>
  <div v-if="days.length" class="day-bars" aria-hidden="true">
    <div v-for="day in days" :key="day.day" class="day-bar" :title="`${formatDay(day.day)} · ${day.count}`">
      <span :style="{ height: height(day.count) }" />
    </div>
  </div>
</template>
