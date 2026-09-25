<script setup lang="ts">
import { recordLayerLabel } from '@/lib/labels'
import type { RecordLayer } from '@/types/models'

defineProps<{ layer: RecordLayer }>()
</script>

<template>
  <span class="prov" :data-prov="layer">{{ recordLayerLabel(layer) }}</span>
</template>
