<script setup lang="ts">
import ProvenanceLegend from '@/components/ProvenanceLegend.vue'
import { onMounted, onUnmounted, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    kicker: string
    title: string
    description: string
    showLegend?: boolean
  }>(),
  { showLegend: true },
)

function applyTitle(title: string): void {
  document.title = `${title} · Switchboard`
}

watch(
  () => props.title,
  (title) => {
    applyTitle(title)
  },
)

onMounted(() => {
  applyTitle(props.title)
})

onUnmounted(() => {
  document.title = 'Switchboard'
})
</script>

<template>
  <header class="page-head">
    <div>
      <p class="kicker">{{ kicker }}</p>
      <h1>{{ title }}</h1>
      <p class="lede">{{ description }}</p>
    </div>
    <ProvenanceLegend v-if="showLegend" />
  </header>
</template>
