<script setup lang="ts">
import ClassificationTag from '@/components/ClassificationTag.vue'
import IndicatorChips from '@/components/IndicatorChips.vue'
import IntelligenceList from '@/components/IntelligenceList.vue'
import LatencyStrip from '@/components/LatencyStrip.vue'
import LoadError from '@/components/LoadError.vue'
import PageHeader from '@/components/PageHeader.vue'
import ProvenanceBadge from '@/components/ProvenanceBadge.vue'
import StateTag from '@/components/StateTag.vue'
import StatusPill from '@/components/StatusPill.vue'
import TranscriptLog from '@/components/TranscriptLog.vue'
import { useNow } from '@/composables/useNow'
import { formatDuration, formatOffset, formatPercent, formatTimestamp } from '@/lib/format'
import { conversationStateLabel, eventTypeLabel, observationCategoryLabel } from '@/lib/labels'
import { useCallDetailStore } from '@/stores/callDetail'
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const store = useCallDetailStore()
const now = useNow()

const callId = computed(() => (typeof route.params.id === 'string' ? route.params.id : ''))

watch(
  callId,
  (id) => {
    if (id) void store.load(id)
  },
  { immediate: true },
)

const call = computed(() => store.detail)

const keyFindings = computed(() => {
  const current = call.value
  if (!current) return []
  const wanted = new Set(current.gaps.key_finding_ids)
  return current.findings.filter((finding) => wanted.has(finding.id))
})

const elapsedMs = computed(() => {
  const current = call.value
  if (!current) return 0
  if (current.session.ended_at) return current.gaps.duration_ms
  return Math.max(0, now.value - Date.parse(current.session.started_at))
})

function payloadText(payload: Record<string, unknown>): string {
  const entries = Object.entries(payload).slice(0, 6)
  if (entries.length === 0) return '—'
  return entries
    .map(([key, value]) => {
      const rendered = typeof value === 'string' ? value : JSON.stringify(value)
      return `${key}=${rendered}`
    })
    .join(' · ')
}

function reload(): void {
  if (callId.value) void store.load(callId.value)
}
</script>

<template>
  <section class="page">
    <p v-if="store.loading" class="empty">Loading call {{ callId }}…</p>
    <LoadError v-else-if="store.error" :message="store.error" @retry="reload" />
    <div v-else-if="store.notFound" class="empty" data-testid="call-missing">
      <h1>Call not in the mock catalog</h1>
      <p>No fixture is loaded for {{ callId }}. The read API would return call_not_found.</p>
      <router-link to="/dashboard/calls">Back to call history</router-link>
    </div>
    <template v-else-if="call">
      <PageHeader
        kicker="Call record"
        :title="call.session.caller_number_e164"
        description="Session and transcript are observations. Turns and findings are interpretations. Attributions link the call to a campaign."
      />
      <div class="detail-head">
        <div class="inline-tags">
          <StatusPill :status="call.session.state" />
          <StateTag :state="call.gaps.conversation_state" :layer="call.gaps.conversation_state_record_layer" />
          <ClassificationTag :classification="call.gaps.classification" />
        </div>
        <p class="mono">{{ call.session.external_call_id }} · {{ call.session.id }}</p>
        <div class="stage-actions">
          <router-link to="/dashboard/calls">All calls</router-link>
          <router-link v-if="call.gaps.campaign_id" :to="`/dashboard/campaigns/${call.gaps.campaign_id}`">
            {{ call.gaps.campaign_label }}
          </router-link>
          <router-link
            v-if="call.session.state === 'in_progress' || call.session.state === 'ringing'"
            :to="{ path: '/dashboard/live', query: { call: call.session.id } }"
          >
            Live board
          </router-link>
        </div>
      </div>
      <dl class="stats">
        <div>
          <dt>Started</dt>
          <dd>{{ formatTimestamp(call.session.started_at) }}</dd>
        </div>
        <div>
          <dt>Ended</dt>
          <dd>{{ call.session.ended_at ? formatTimestamp(call.session.ended_at) : 'Still up' }}</dd>
        </div>
        <div>
          <dt>{{ call.session.ended_at ? 'Duration' : 'Elapsed' }}</dt>
          <dd class="mono">{{ formatDuration(elapsedMs) }}</dd>
        </div>
        <div>
          <dt>Engagement</dt>
          <dd class="mono">
            {{ formatDuration(call.gaps.engagement_duration_ms) }}
            <span v-if="!call.session.ended_at" class="muted">at load</span>
          </dd>
        </div>
      </dl>
      <p v-if="call.session.end_reason" class="caption">End reason: {{ call.session.end_reason }}</p>
      <LatencyStrip
        :stt-ms="call.gaps.pipeline.stt_ms"
        :select-ms="call.gaps.pipeline.select_ms"
        :tts-ms="call.gaps.pipeline.tts_ms"
        :e2e-ms="call.gaps.pipeline.e2e_ms"
        :sampled-at="call.gaps.pipeline.sampled_at"
      />
      <nav class="anchors" aria-label="Call sections">
        <a href="#timeline">Timeline</a>
        <a href="#transcript">Transcript</a>
        <a href="#states">States</a>
        <a href="#observations">Paired reads</a>
        <a href="#correlation">Attribution</a>
        <a href="#technical">Events</a>
        <a href="#intelligence">Findings</a>
      </nav>

      <section id="timeline" class="section">
        <h2>Call timeline</h2>
        <p class="caption">Rows with an event name are bus events. A note is an operator gap, not an EventType.</p>
        <ol class="timeline">
          <li v-for="entry in call.gaps.timeline" :key="entry.id">
            <span class="mono">{{ formatOffset(entry.offset_ms) }}</span>
            <span class="kind">{{ entry.event_type ? eventTypeLabel(entry.event_type) : 'Note' }}</span>
            <div>
              <p class="item-title">{{ entry.title }}</p>
              <p class="muted">{{ entry.detail }}</p>
              <p v-if="entry.event_type" class="mono muted">{{ entry.event_type }}</p>
            </div>
          </li>
        </ol>
      </section>

      <section id="transcript" class="section">
        <h2>Transcript</h2>
        <TranscriptLog :turns="call.transcript" />
      </section>

      <section id="states" class="section">
        <h2>Dialogue beats</h2>
        <p class="caption">This chain is not CallState. The session state is the pill in the header.</p>
        <ol class="timeline">
          <li v-for="transition in call.gaps.state_transitions" :key="transition.id">
            <span class="mono">{{ formatOffset(transition.offset_ms) }}</span>
            <ProvenanceBadge :layer="transition.record_layer" />
            <div>
              <p class="item-title">
                {{ transition.from ? conversationStateLabel(transition.from) : 'Start' }}
                →
                {{ conversationStateLabel(transition.to) }}
              </p>
              <p class="muted">{{ transition.reason }}</p>
            </div>
          </li>
        </ol>
      </section>

      <section id="observations" class="section">
        <h2>Paired reads</h2>
        <p class="caption">
          Raw text is an observation. The reading beside it is an interpretation. This pairing is not a stored table.
        </p>
        <div class="obs-list">
          <article v-for="observation in call.gaps.paired_reads" :key="observation.id" class="obs">
            <header>
              <span class="mono">{{ formatOffset(observation.offset_ms) }}</span>
              <span class="kind">{{ observationCategoryLabel(observation.category) }}</span>
            </header>
            <div class="obs-grid">
              <div class="obs-raw" :data-prov="observation.raw.record_layer">
                <div class="intel-top">
                  <h3>Observation</h3>
                  <ProvenanceBadge :layer="observation.raw.record_layer" />
                </div>
                <p>{{ observation.raw.text }}</p>
              </div>
              <div class="obs-derived" :data-prov="observation.interpretation?.record_layer">
                <template v-if="observation.interpretation">
                  <div class="intel-top">
                    <h3>Interpretation</h3>
                    <ProvenanceBadge :layer="observation.interpretation.record_layer" />
                  </div>
                  <p>{{ observation.interpretation.text }}</p>
                </template>
                <p v-else class="muted">No interpretation recorded.</p>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section id="correlation" class="section">
        <h2>Attribution</h2>
        <p class="caption">CampaignAttribution cites findings. The chips under a note are a display gap.</p>
        <ol v-if="call.attributions.length" class="reason-list">
          <li v-for="row in call.attributions" :key="row.id" class="reason">
            <div class="intel-top">
              <ProvenanceBadge layer="attribution" />
              <span class="mono">{{ formatPercent(row.confidence) }}</span>
              <span class="mono">{{ row.method }} {{ row.method_version }}</span>
              <router-link :to="`/dashboard/campaigns/${row.campaign_id}`">{{ call.gaps.campaign_label ?? row.campaign_id }}</router-link>
            </div>
            <p>{{ row.rationale }}</p>
            <div class="meter reason-meter">
              <span :style="{ width: `${Math.round(row.confidence * 100)}%` }" />
            </div>
            <p class="caption">Supporting findings: {{ row.supporting_finding_ids.join(', ') }}</p>
          </li>
        </ol>
        <p v-else class="empty">No campaign attribution on this call.</p>
        <ol class="reason-list">
          <li v-for="reason in call.gaps.correlation_notes" :key="reason.id" class="reason">
            <div class="intel-top">
              <ProvenanceBadge :layer="reason.record_layer" />
              <span class="mono">{{ formatPercent(reason.score) }}</span>
              <router-link v-if="reason.campaign_id" :to="`/dashboard/campaigns/${reason.campaign_id}`">
                {{ reason.campaign_label }}
              </router-link>
              <span v-else class="muted">No campaign</span>
            </div>
            <p class="item-title">{{ reason.summary }}</p>
            <p>{{ reason.explanation }}</p>
            <ul v-if="reason.matched_on.length" class="chips">
              <li v-for="match in reason.matched_on" :key="match.label">
                <ProvenanceBadge :layer="match.record_layer" />
                <span>{{ match.label }}</span>
              </li>
            </ul>
          </li>
        </ol>
      </section>

      <section id="technical" class="section">
        <h2>Events</h2>
        <p class="caption">event_type values are the EventType taxonomy. offset_ms is not on EventEnvelope.</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Offset</th>
                <th>Event</th>
                <th>Producer</th>
                <th>Payload</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="event in call.events" :key="event.event_id">
                <td class="mono">{{ formatOffset(event.offset_ms) }}</td>
                <td>
                  <div>{{ eventTypeLabel(event.event_type) }}</div>
                  <div class="mono muted">{{ event.event_type }}</div>
                </td>
                <td class="mono">{{ event.producer }}</td>
                <td>{{ payloadText(event.payload) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section id="intelligence" class="section">
        <h2>Findings</h2>
        <p class="caption">Key findings also shown on the history row. Status stays proposed until an operator accepts or rejects.</p>
        <IndicatorChips :items="keyFindings" />
        <IntelligenceList :items="call.findings" empty="No findings for this call." />
      </section>
    </template>
  </section>
</template>
