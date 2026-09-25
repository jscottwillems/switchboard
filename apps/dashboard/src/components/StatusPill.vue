<script setup lang="ts">
import { callStatusLabel } from '@/lib/labels'
import type { CallStatus } from '@/types/models'

defineProps<{ status: CallStatus }>()
</script>

<template>
  <span class="status-pill" :data-status="status">{{ callStatusLabel(status) }}</span>
</template>
