<script setup lang="ts">
import ProvenanceBadge from '@/components/ProvenanceBadge.vue'
</script>

<template>
  <div class="legend" aria-label="Record layers">
    <span class="legend-label">Record layer</span>
    <ProvenanceBadge layer="observation" />
    <ProvenanceBadge layer="interpretation" />
    <ProvenanceBadge layer="attribution" />
  </div>
</template>
