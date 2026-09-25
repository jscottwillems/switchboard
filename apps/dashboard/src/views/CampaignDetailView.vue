<script setup lang="ts">
import ActivityHeatmap from '@/components/ActivityHeatmap.vue'
import ClassificationTag from '@/components/ClassificationTag.vue'
import IndicatorChips from '@/components/IndicatorChips.vue'
import IntelligenceList from '@/components/IntelligenceList.vue'
import LoadError from '@/components/LoadError.vue'
import PageHeader from '@/components/PageHeader.vue'
import ProvenanceBadge from '@/components/ProvenanceBadge.vue'
import StateTag from '@/components/StateTag.vue'
import StatusPill from '@/components/StatusPill.vue'
import { formatDuration, formatPercent, formatTimestamp } from '@/lib/format'
import { campaignStatusLabel } from '@/lib/labels'
import { useCampaignDetailStore } from '@/stores/campaignDetail'
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const store = useCampaignDetailStore()

const campaignId = computed(() => (typeof route.params.id === 'string' ? route.params.id : ''))

watch(
  campaignId,
  (id) => {
    if (id) void store.load(id)
  },
  { immediate: true },
)

const campaign = computed(() => store.detail)

function reload(): void {
  if (campaignId.value) void store.load(campaignId.value)
}
</script>

<template>
  <section class="page">
    <p v-if="store.loading" class="empty">Loading campaign {{ campaignId }}…</p>
    <LoadError v-else-if="store.error" :message="store.error" @retry="reload" />
    <div v-else-if="store.notFound" class="empty" data-testid="campaign-missing">
      <h1>Campaign not in the mock catalog</h1>
      <p>No fixture is loaded for {{ campaignId }}.</p>
      <router-link to="/dashboard/campaigns">Back to campaigns</router-link>
    </div>
    <template v-else-if="campaign">
      <PageHeader kicker="Campaign" :title="campaign.name" :description="campaign.summary" />
      <div class="detail-head">
        <div class="inline-tags">
          <span class="status-pill" :data-campaign="campaign.status">{{ campaignStatusLabel(campaign.status) }}</span>
          <ClassificationTag :classification="campaign.classification" />
        </div>
        <p class="mono">{{ campaign.id }}</p>
        <router-link to="/dashboard/campaigns">All campaigns</router-link>
      </div>
      <dl class="stats">
        <div>
          <dt>Calls</dt>
          <dd>{{ campaign.callCount }}</dd>
        </div>
        <div>
          <dt>Active now</dt>
          <dd>{{ campaign.activeCallCount }}</dd>
        </div>
        <div>
          <dt>Linked records</dt>
          <dd>{{ campaign.relatedCalls.length }}</dd>
        </div>
        <div>
          <dt>First seen</dt>
          <dd>{{ formatTimestamp(campaign.firstSeenAt) }}</dd>
        </div>
        <div>
          <dt>Last seen</dt>
          <dd>{{ formatTimestamp(campaign.lastSeenAt) }}</dd>
        </div>
      </dl>
      <p class="caption">Call count is the aggregate volume. Linked records are the calls this mock can open.</p>

      <section id="timeline" class="section">
        <h2>Campaign timeline</h2>
        <ol class="timeline">
          <li v-for="entry in campaign.timeline" :key="entry.id">
            <span class="mono">{{ formatTimestamp(entry.at) }}</span>
            <span class="kind">Event</span>
            <div>
              <p class="item-title">{{ entry.title }}</p>
              <p class="muted">{{ entry.detail }}</p>
            </div>
          </li>
        </ol>
      </section>

      <section id="calls" class="section">
        <h2>Related calls</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Started</th>
                <th>Duration</th>
                <th>Engagement</th>
                <th>Status</th>
                <th>State</th>
                <th>Classification</th>
                <th>Indicators</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="related in campaign.relatedCalls" :key="related.id">
                <td>
                  <router-link :to="`/dashboard/calls/${related.id}`">{{ formatTimestamp(related.startedAt) }}</router-link>
                  <div class="mono muted">{{ related.id }}</div>
                </td>
                <td class="mono">{{ formatDuration(related.durationMs) }}</td>
                <td class="mono">{{ formatDuration(related.engagementDurationMs) }}</td>
                <td><StatusPill :status="related.status" /></td>
                <td><StateTag :state="related.conversationState" :provenance="related.stateProvenance" /></td>
                <td><ClassificationTag :classification="related.classification" /></td>
                <td><IndicatorChips :items="related.keyIndicators" /></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <div class="split">
        <section id="phrases" class="section">
          <h2>Common script phrases</h2>
          <IntelligenceList :items="campaign.commonScriptPhrases" empty="No shared phrases." />
        </section>
        <section id="indicators" class="section">
          <h2>Shared indicators</h2>
          <IntelligenceList :items="campaign.sharedIndicators" empty="No shared indicators." />
        </section>
      </div>

      <section id="similarity" class="section">
        <h2>Similarity explanations</h2>
        <ol class="reason-list">
          <li v-for="item in campaign.similarity" :key="item.callId" class="reason">
            <div class="intel-top">
              <ProvenanceBadge :provenance="item.provenance" />
              <span class="mono">{{ formatPercent(item.score) }}</span>
              <router-link :to="`/dashboard/calls/${item.callId}`">{{ item.callId }}</router-link>
            </div>
            <p>{{ item.explanation }}</p>
            <div class="meter reason-meter">
              <span :style="{ width: `${Math.round(item.score * 100)}%` }" />
            </div>
          </li>
        </ol>
      </section>

      <section id="activity" class="section">
        <h2>Activity by day and hour</h2>
        <ActivityHeatmap :activity="campaign.activity" />
      </section>
    </template>
  </section>
</template>
