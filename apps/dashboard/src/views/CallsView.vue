<script setup lang="ts">
import ClassificationTag from '@/components/ClassificationTag.vue'
import IndicatorChips from '@/components/IndicatorChips.vue'
import LoadError from '@/components/LoadError.vue'
import PageHeader from '@/components/PageHeader.vue'
import StateTag from '@/components/StateTag.vue'
import StatusPill from '@/components/StatusPill.vue'
import { opsDataSource } from '@/data/client'
import { campaignCaption, formatDuration, formatTimestamp } from '@/lib/format'
import { classificationLabel } from '@/lib/labels'
import { useCallHistoryStore } from '@/stores/callHistory'
import { CLASSIFICATIONS, type Classification } from '@/types/models'
import { computed, onMounted, ref } from 'vue'

const store = useCallHistoryStore()
const query = ref('')
const classification = ref<'all' | Classification>('all')
const campaign = ref('all')

const description =
  opsDataSource === 'mock'
    ? 'Finished sessions. Duration and engagement are operator gaps. Classification is not on CallSession.'
    : 'Stored sessions from GET /v1/calls, newest started_at first. Carrier id, findings, and campaign links are on the call record.'

onMounted(() => {
  void store.load()
})

const campaignNames = computed(() => {
  const names = new Set<string>()
  for (const call of store.calls) {
    if (call.gaps.campaign_label) names.add(call.gaps.campaign_label)
  }
  return [...names].sort((left, right) => left.localeCompare(right))
})

const filtered = computed(() => {
  const needle = query.value.trim().toLowerCase()
  return store.calls.filter((call) => {
    if (classification.value !== 'all' && call.gaps.classification.label !== classification.value) return false
    if (campaign.value === 'none' && call.gaps.campaign_id !== null) return false
    if (campaign.value !== 'all' && campaign.value !== 'none' && call.gaps.campaign_label !== campaign.value) return false
    if (!needle) return true
    const indicators = call.key_findings.map((item) => `${item.raw_quote} ${item.value}`).join(' ')
    const haystack = [
      call.session.id,
      call.session.external_call_id,
      call.gaps.campaign_label ?? '',
      call.session.caller_number_e164,
      indicators,
    ]
      .join(' ')
      .toLowerCase()
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
      :description="description"
    />
    <div class="toolbar">
      <p class="caption">{{ store.calls.length }} stored</p>
      <button type="button" @click="store.load()">Refresh</button>
    </div>
    <LoadError v-if="store.error" :message="store.error" @retry="store.load()" />
    <p v-if="store.loading && !store.loaded" class="empty">Loading call history…</p>
    <template v-else-if="store.loaded">
      <form class="filters" @submit.prevent>
        <label>
          Search
          <input v-model="query" type="search" placeholder="Id, number, campaign, finding" />
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
      <p v-if="store.calls.length === 0" class="empty" data-testid="calls-empty">No calls yet.</p>
      <div v-else class="table-wrap" data-testid="call-table">
        <table>
          <thead>
            <tr>
              <th>Started</th>
              <th>Caller</th>
              <th>Duration</th>
              <th>Engagement</th>
              <th>State</th>
              <th>Classification</th>
              <th>Campaign</th>
              <th>Dialogue</th>
              <th>Key findings</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="call in filtered" :key="call.session.id">
              <td>
                <router-link :to="`/dashboard/calls/${call.session.id}`">{{ formatTimestamp(call.session.started_at) }}</router-link>
                <div v-if="call.session.external_call_id" class="mono muted">{{ call.session.external_call_id }}</div>
              </td>
              <td class="mono">{{ call.session.caller_number_e164 }}</td>
              <td class="mono">{{ formatDuration(call.gaps.duration_ms) }}</td>
              <td class="mono">{{ formatDuration(call.gaps.engagement_duration_ms) }}</td>
              <td><StatusPill :status="call.session.state" /></td>
              <td><ClassificationTag :classification="call.gaps.classification" /></td>
              <td>
                <router-link v-if="call.gaps.campaign_id" :to="`/dashboard/campaigns/${call.gaps.campaign_id}`">
                  {{ campaignCaption(call.gaps.campaign_id, call.gaps.campaign_label) }}
                </router-link>
                <span v-else class="muted">Unlinked</span>
              </td>
              <td>
                <StateTag
                  v-if="call.gaps.conversation_state"
                  :state="call.gaps.conversation_state"
                  :layer="call.gaps.conversation_state_record_layer ?? undefined"
                />
                <span v-else class="muted">—</span>
              </td>
              <td><IndicatorChips :items="call.key_findings" /></td>
            </tr>
          </tbody>
        </table>
        <p v-if="filtered.length === 0" class="empty">No calls match this filter.</p>
      </div>
    </template>
  </section>
</template>
