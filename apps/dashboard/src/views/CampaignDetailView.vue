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
import { campaignStatusLabel, eventTypeLabel } from '@/lib/labels'
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
      <p>No fixture is loaded for {{ campaignId }}. The read API would return campaign_not_found.</p>
      <router-link to="/dashboard/campaigns">Back to campaigns</router-link>
    </div>
    <template v-else-if="campaign">
      <PageHeader kicker="Campaign" :title="campaign.campaign.label" :description="campaign.campaign.summary ?? ''" />
      <div class="detail-head">
        <div class="inline-tags">
          <span class="status-pill" :data-campaign="campaign.campaign.status">{{ campaignStatusLabel(campaign.campaign.status) }}</span>
          <ClassificationTag :classification="campaign.gaps.classification" />
        </div>
        <p class="mono">{{ campaign.campaign.id }}</p>
        <router-link to="/dashboard/campaigns">All campaigns</router-link>
      </div>
      <dl class="stats">
        <div>
          <dt>Calls</dt>
          <dd>{{ campaign.gaps.call_count }}</dd>
        </div>
        <div>
          <dt>In progress</dt>
          <dd>{{ campaign.gaps.active_call_count }}</dd>
        </div>
        <div>
          <dt>Linked records</dt>
          <dd>{{ campaign.related_calls.length }}</dd>
        </div>
        <div>
          <dt>Opened</dt>
          <dd>{{ formatTimestamp(campaign.campaign.created_at) }}</dd>
        </div>
        <div>
          <dt>Updated</dt>
          <dd>{{ formatTimestamp(campaign.campaign.updated_at) }}</dd>
        </div>
      </dl>
      <p class="caption">
        GET /v1/campaigns/{id} returns Campaign only. Call count, the timeline, and linked calls are gaps. Opened is created_at. Updated is updated_at.
      </p>

      <section id="timeline" class="section">
        <h2>Campaign timeline</h2>
        <ol class="timeline">
          <li v-for="entry in campaign.gaps.timeline" :key="entry.id">
            <span class="mono">{{ formatTimestamp(entry.at) }}</span>
            <span class="kind">{{ eventTypeLabel(entry.event_type) }}</span>
            <div>
              <p class="item-title">{{ entry.title }}</p>
              <p class="muted">{{ entry.detail }}</p>
              <p class="mono muted">{{ entry.event_type }}</p>
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
                <th>State</th>
                <th>Dialogue</th>
                <th>Classification</th>
                <th>Findings</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="related in campaign.related_calls" :key="related.session.id">
                <td>
                  <router-link :to="`/dashboard/calls/${related.session.id}`">{{ formatTimestamp(related.session.started_at) }}</router-link>
                  <div class="mono muted">{{ related.session.external_call_id }}</div>
                </td>
                <td class="mono">{{ formatDuration(related.gaps.duration_ms) }}</td>
                <td class="mono">{{ formatDuration(related.gaps.engagement_duration_ms) }}</td>
                <td><StatusPill :status="related.session.state" /></td>
                <td>
                  <StateTag :state="related.gaps.conversation_state" :layer="related.gaps.conversation_state_record_layer" />
                </td>
                <td><ClassificationTag :classification="related.gaps.classification" /></td>
                <td><IndicatorChips :items="related.key_findings" /></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <div class="split">
        <section id="phrases" class="section">
          <h2>Common script phrases</h2>
          <p class="caption">Not IntelligenceFinding rows. A finding has to cite one call.</p>
          <IntelligenceList :items="campaign.gaps.script_phrases" empty="No shared phrases." />
        </section>
        <section id="indicators" class="section">
          <h2>Shared indicators</h2>
          <IntelligenceList :items="campaign.gaps.shared_indicators" empty="No shared indicators." />
        </section>
      </div>

      <section id="similarity" class="section">
        <h2>Similarity explanations</h2>
        <ol class="reason-list">
          <li v-for="item in campaign.gaps.similarity" :key="item.call_id" class="reason">
            <div class="intel-top">
              <ProvenanceBadge :layer="item.record_layer" />
              <span class="mono">{{ formatPercent(item.score) }}</span>
              <router-link :to="`/dashboard/calls/${item.call_id}`">{{ item.external_call_id }}</router-link>
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
        <ActivityHeatmap :activity="campaign.gaps.activity" />
      </section>
    </template>
  </section>
</template>
