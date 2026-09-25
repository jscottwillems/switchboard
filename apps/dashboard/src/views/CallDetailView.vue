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
import {
  conversationStateLabel,
  observationCategoryLabel,
  severityLabel,
  technicalSourceLabel,
  timelineKindLabel,
} from '@/lib/labels'
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

const elapsedMs = computed(() => {
  const current = call.value
  if (!current) return 0
  if (current.endedAt) return current.durationMs
  return Math.max(0, now.value - Date.parse(current.startedAt))
})

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
      <p>No fixture is loaded for {{ callId }}.</p>
      <router-link to="/dashboard/calls">Back to call history</router-link>
    </div>
    <template v-else-if="call">
      <PageHeader
        kicker="Call record"
        :title="call.callerNumberMasked"
        description="Timeline, transcript, state changes, raw observations, interpretations, correlation, and technical events."
      />
      <div class="detail-head">
        <div class="inline-tags">
          <StatusPill :status="call.status" />
          <StateTag :state="call.conversationState" :provenance="call.stateProvenance" />
          <ClassificationTag :classification="call.classification" />
        </div>
        <p class="mono">{{ call.id }}</p>
        <div class="stage-actions">
          <router-link to="/dashboard/calls">All calls</router-link>
          <router-link v-if="call.campaignId" :to="`/dashboard/campaigns/${call.campaignId}`">
            {{ call.campaignName }}
          </router-link>
          <router-link v-if="call.status === 'active'" :to="{ path: '/dashboard/live', query: { call: call.id } }">
            Live board
          </router-link>
        </div>
      </div>
      <dl class="stats">
        <div>
          <dt>Started</dt>
          <dd>{{ formatTimestamp(call.startedAt) }}</dd>
        </div>
        <div>
          <dt>Ended</dt>
          <dd>{{ call.endedAt ? formatTimestamp(call.endedAt) : 'Still up' }}</dd>
        </div>
        <div>
          <dt>{{ call.status === 'active' ? 'Elapsed' : 'Duration' }}</dt>
          <dd class="mono">{{ formatDuration(elapsedMs) }}</dd>
        </div>
        <div>
          <dt>Engagement</dt>
          <dd class="mono">
            {{ formatDuration(call.engagementDurationMs) }}
            <span v-if="call.status === 'active'" class="muted">at load</span>
          </dd>
        </div>
      </dl>
      <LatencyStrip
        :stt-ms="call.pipeline.sttMs"
        :llm-ms="call.pipeline.llmMs"
        :tts-ms="call.pipeline.ttsMs"
        :e2e-ms="call.pipeline.e2eMs"
        :sampled-at="call.pipeline.sampledAt"
      />
      <nav class="anchors" aria-label="Call sections">
        <a href="#timeline">Timeline</a>
        <a href="#transcript">Transcript</a>
        <a href="#states">States</a>
        <a href="#observations">Observations</a>
        <a href="#correlation">Correlation</a>
        <a href="#technical">Technical</a>
        <a href="#intelligence">Intelligence</a>
      </nav>

      <section id="timeline" class="section">
        <h2>Call timeline</h2>
        <ol class="timeline">
          <li v-for="entry in call.timeline" :key="entry.id">
            <span class="mono">{{ formatOffset(entry.offsetMs) }}</span>
            <span class="kind">{{ timelineKindLabel(entry.kind) }}</span>
            <div>
              <p class="item-title">{{ entry.title }}</p>
              <p class="muted">{{ entry.detail }}</p>
            </div>
          </li>
        </ol>
      </section>

      <section id="transcript" class="section">
        <h2>Transcript</h2>
        <TranscriptLog :turns="call.transcript" />
      </section>

      <section id="states" class="section">
        <h2>Conversation state transitions</h2>
        <ol class="timeline">
          <li v-for="transition in call.stateTransitions" :key="transition.id">
            <span class="mono">{{ formatOffset(transition.offsetMs) }}</span>
            <ProvenanceBadge :provenance="transition.provenance" />
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
        <h2>Structured observations</h2>
        <p class="caption">Raw is what was captured. Interpretation is a reading of that capture. Each side carries its own provenance.</p>
        <div class="obs-list">
          <article v-for="observation in call.observations" :key="observation.id" class="obs">
            <header>
              <span class="mono">{{ formatOffset(observation.offsetMs) }}</span>
              <span class="kind">{{ observationCategoryLabel(observation.category) }}</span>
            </header>
            <div class="obs-grid">
              <div class="obs-raw" :data-prov="observation.raw.provenance">
                <div class="intel-top">
                  <h3>Raw observation</h3>
                  <ProvenanceBadge :provenance="observation.raw.provenance" />
                </div>
                <p>{{ observation.raw.text }}</p>
              </div>
              <div
                class="obs-derived"
                :data-prov="observation.interpretation ? observation.interpretation.provenance : undefined"
              >
                <template v-if="observation.interpretation">
                  <div class="intel-top">
                    <h3>Interpretation</h3>
                    <ProvenanceBadge :provenance="observation.interpretation.provenance" />
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
        <h2>Correlation reasoning</h2>
        <ol class="reason-list">
          <li v-for="reason in call.correlation" :key="reason.id" class="reason">
            <div class="intel-top">
              <ProvenanceBadge :provenance="reason.provenance" />
              <span class="mono">{{ formatPercent(reason.score) }}</span>
              <router-link v-if="reason.campaignId" :to="`/dashboard/campaigns/${reason.campaignId}`">
                {{ reason.campaignName }}
              </router-link>
              <span v-else class="muted">No campaign</span>
            </div>
            <p class="item-title">{{ reason.summary }}</p>
            <p>{{ reason.explanation }}</p>
            <div class="meter reason-meter">
              <span :style="{ width: `${Math.round(reason.score * 100)}%` }" />
            </div>
            <ul v-if="reason.matchedOn.length" class="chips">
              <li v-for="match in reason.matchedOn" :key="match.label">
                <ProvenanceBadge :provenance="match.provenance" />
                <span>{{ match.label }}</span>
              </li>
            </ul>
            <p v-else class="caption">No indicators were attached to this reasoning.</p>
          </li>
        </ol>
      </section>

      <section id="technical" class="section">
        <h2>Technical events</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Offset</th>
                <th>Source</th>
                <th>Severity</th>
                <th>Message</th>
                <th>Attributes</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="event in call.technicalEvents" :key="event.id">
                <td class="mono">{{ formatOffset(event.offsetMs) }}</td>
                <td>{{ technicalSourceLabel(event.source) }}</td>
                <td><span class="severity" :data-severity="event.severity">{{ severityLabel(event.severity) }}</span></td>
                <td>{{ event.message }}</td>
                <td>
                  <ul class="attr-list">
                    <li v-for="attribute in event.attributes" :key="attribute.key">
                      <span class="mono">{{ attribute.key }}</span>
                      {{ attribute.value }}
                    </li>
                  </ul>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section id="intelligence" class="section">
        <h2>Extracted intelligence</h2>
        <p class="caption">Key indicators also shown on the history row:</p>
        <IndicatorChips :items="call.keyIndicators" />
        <IntelligenceList :items="call.intelligence" empty="No intelligence extracted for this call." />
      </section>
    </template>
  </section>
</template>
