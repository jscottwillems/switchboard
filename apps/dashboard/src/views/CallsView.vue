<script setup lang="ts">
import ClassificationTag from '@/components/ClassificationTag.vue'
import IndicatorChips from '@/components/IndicatorChips.vue'
import LoadError from '@/components/LoadError.vue'
import PageHeader from '@/components/PageHeader.vue'
import StateTag from '@/components/StateTag.vue'
import StatusPill from '@/components/StatusPill.vue'
import { formatDuration, formatTimestamp } from '@/lib/format'
import { classificationLabel } from '@/lib/labels'
import { useCallHistoryStore } from '@/stores/callHistory'
import { CLASSIFICATIONS, type Classification } from '@/types/models'
import { computed, onMounted, ref } from 'vue'

const store = useCallHistoryStore()
const query = ref('')
const classification = ref<'all' | Classification>('all')
const campaign = ref('all')

onMounted(() => {
  void store.load()
})

const campaignNames = computed(() => {
  const names = new Set<string>()
  for (const call of store.calls) {
    if (call.campaignName) names.add(call.campaignName)
  }
  return [...names].sort((left, right) => left.localeCompare(right))
})

const filtered = computed(() => {
  const needle = query.value.trim().toLowerCase()
  return store.calls.filter((call) => {
    if (classification.value !== 'all' && call.classification.label !== classification.value) return false
    if (campaign.value === 'none' && call.campaignId !== null) return false
    if (campaign.value !== 'all' && campaign.value !== 'none' && call.campaignName !== campaign.value) return false
    if (!needle) return true
    const indicators = call.keyIndicators.map((item) => `${item.label} ${item.value}`).join(' ')
    const haystack = [call.id, call.campaignName ?? '', call.callerNumberMasked, indicators].join(' ').toLowerCase()
    return haystack.includes(needle)
  })
})

function onClassification(event: Event): void {
  const value = (event.target as HTMLSelectElement).value
  classification.value = value === 'all' ? 'all' : (value as Classification)
}

function onCampaign(event: Event): void {
  campaign.value = (event.target as HTMLSelectElement).value
}
</script>

<template>
  <section class="page">
    <PageHeader
      kicker="History"
      title="Call history"
      description="Answered calls with duration, engagement, classification, campaign, and key indicators."
    />
    <LoadError v-if="store.error" :message="store.error" @retry="store.load()" />
    <p v-if="store.loading && !store.loaded" class="empty">Loading call history…</p>
    <template v-else-if="store.loaded">
      <form class="filters" @submit.prevent>
        <label>
          Search
          <input v-model="query" type="search" placeholder="Id, number, campaign, indicator" />
        </label>
        <label>
          Classification
          <select :value="classification" @change="onClassification">
            <option value="all">All</option>
            <option v-for="item in CLASSIFICATIONS" :key="item" :value="item">{{ classificationLabel(item) }}</option>
          </select>
        </label>
        <label>
          Campaign
          <select :value="campaign" @change="onCampaign">
            <option value="all">All</option>
            <option value="none">Unlinked</option>
            <option v-for="name in campaignNames" :key="name" :value="name">{{ name }}</option>
          </select>
        </label>
        <p class="caption">{{ filtered.length }} of {{ store.calls.length }}</p>
      </form>
      <div class="table-wrap" data-testid="call-table">
        <table>
          <thead>
            <tr>
              <th>Started</th>
              <th>Caller</th>
              <th>Duration</th>
              <th>Engagement</th>
              <th>Status</th>
              <th>Classification</th>
              <th>Campaign</th>
              <th>State</th>
              <th>Key indicators</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="call in filtered" :key="call.id">
              <td>
                <router-link :to="`/dashboard/calls/${call.id}`">{{ formatTimestamp(call.startedAt) }}</router-link>
                <div class="mono muted">{{ call.id }}</div>
              </td>
              <td class="mono">{{ call.callerNumberMasked }}</td>
              <td class="mono">{{ formatDuration(call.durationMs) }}</td>
              <td class="mono">{{ formatDuration(call.engagementDurationMs) }}</td>
              <td><StatusPill :status="call.status" /></td>
              <td><ClassificationTag :classification="call.classification" /></td>
              <td>
                <router-link v-if="call.campaignId" :to="`/dashboard/campaigns/${call.campaignId}`">
                  {{ call.campaignName }}
                </router-link>
                <span v-else class="muted">Unlinked</span>
              </td>
              <td><StateTag :state="call.conversationState" :provenance="call.stateProvenance" /></td>
              <td><IndicatorChips :items="call.keyIndicators" /></td>
            </tr>
            <tr v-if="filtered.length === 0">
              <td colspan="9" class="empty">No calls match these filters.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>
