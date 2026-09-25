<script setup lang="ts">
import { callStateLabel } from '@/lib/labels'
import type { CallState } from '@/types/models'

defineProps<{ status: CallState }>()
</script>

<template>
  <span class="status-pill" :data-status="status">{{ callStateLabel(status) }}</span>
</template>
