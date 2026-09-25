<script setup lang="ts">
import { useNow } from '@/composables/useNow'
import { formatClock } from '@/lib/format'
import { useLiveStore } from '@/stores/live'
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'

const now = useNow()
const live = useLiveStore()
const route = useRoute()

function sectionActive(prefix: string): boolean {
  return route.path === prefix || route.path.startsWith(`${prefix}/`)
}

onMounted(() => {
  void live.load()
})
</script>

<template>
  <div class="shell">
    <a class="skip" href="#content">Skip to content</a>
    <header class="topbar">
      <router-link class="brand" to="/dashboard/live">
        <svg viewBox="0 0 32 32" aria-hidden="true">
          <circle cx="16" cy="16" r="10" fill="none" stroke="currentColor" stroke-width="1.5" />
          <path d="M16 16 L25 9" fill="none" stroke="currentColor" stroke-width="1.5" />
          <circle cx="16" cy="16" r="2" fill="currentColor" />
        </svg>
        <span>
          <strong>Switchboard</strong>
          <small>Honeypot ops</small>
        </span>
      </router-link>
      <nav class="nav" aria-label="Primary">
        <router-link to="/dashboard/live" :class="{ 'is-section': sectionActive('/dashboard/live') }">
          Live
          <em v-if="live.loaded">{{ live.calls.length }}</em>
        </router-link>
        <router-link to="/dashboard/calls" :class="{ 'is-section': sectionActive('/dashboard/calls') }">Calls</router-link>
        <router-link to="/dashboard/campaigns" :class="{ 'is-section': sectionActive('/dashboard/campaigns') }">
          Campaigns
        </router-link>
        <router-link to="/dashboard/reports" :class="{ 'is-section': sectionActive('/dashboard/reports') }">Reports</router-link>
        <router-link to="/dashboard/system" :class="{ 'is-section': sectionActive('/dashboard/system') }">System</router-link>
      </nav>
      <div class="top-meta">
        <span class="env-pill">Mock data</span>
        <time class="clock">{{ formatClock(now) }}</time>
      </div>
    </header>
    <main id="content" class="main">
      <router-view />
    </main>
  </div>
</template>
