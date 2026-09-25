<script setup lang="ts">
import { provenanceLabel } from '@/lib/labels'
import type { Provenance } from '@/types/models'

defineProps<{ provenance: Provenance }>()
</script>

<template>
  <span class="prov" :data-prov="provenance">{{ provenanceLabel(provenance) }}</span>
</template>
