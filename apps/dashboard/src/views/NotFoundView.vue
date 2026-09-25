<script setup lang="ts">
import PageHeader from '@/components/PageHeader.vue'
</script>

<template>
  <section class="page">
    <PageHeader
      kicker="Missing"
      title="That route is not on the board"
      description="The ops console covers live calls, call history, campaigns, and system health."
      :show-legend="false"
    />
    <router-link to="/dashboard/live">Go to live calls</router-link>
  </section>
</template>
