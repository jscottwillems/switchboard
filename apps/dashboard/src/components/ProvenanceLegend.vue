<script setup lang="ts">
import BasisMark from '@/components/BasisMark.vue'
import ProvenanceBadge from '@/components/ProvenanceBadge.vue'
</script>

<template>
  <div class="legend" aria-label="How to read intelligence">
    <span class="legend-label">Provenance</span>
    <ProvenanceBadge provenance="observed" />
    <ProvenanceBadge provenance="inferred" />
    <ProvenanceBadge provenance="unverified" />
    <span class="legend-label">Record</span>
    <BasisMark basis="raw" />
    <BasisMark basis="derived" />
  </div>
</template>
