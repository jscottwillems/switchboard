<script setup lang="ts">
import { basisLabel } from '@/lib/labels'
import type { IntelligenceBasis } from '@/types/models'

defineProps<{ basis: IntelligenceBasis }>()
</script>

<template>
  <span class="basis" :data-basis="basis">{{ basisLabel(basis) }}</span>
</template>
