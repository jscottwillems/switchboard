<script setup lang="ts">
import ClassificationTag from '@/components/ClassificationTag.vue'
import IntelligenceList from '@/components/IntelligenceList.vue'
import LatencyStrip from '@/components/LatencyStrip.vue'
import LoadError from '@/components/LoadError.vue'
import PageHeader from '@/components/PageHeader.vue'
import StateTag from '@/components/StateTag.vue'
import StatusPill from '@/components/StatusPill.vue'
import TranscriptLog from '@/components/TranscriptLog.vue'
import { useNow } from '@/composables/useNow'
import { opsDataSource } from '@/data/client'
import { campaignCaption, formatDuration } from '@/lib/format'
import { classificationLabel } from '@/lib/labels'
import { useLiveStore } from '@/stores/live'
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const store = useLiveStore()
const now = useNow()

onMounted(() => {
  void store.load()
})

const selectedId = computed(() => (typeof route.query.call === 'string' ? route.query.call : null))

watch([() => store.calls, selectedId, () => store.loaded], () => {
  if (!store.loaded || store.calls.length === 0) return
  const valid = selectedId.value !== null && store.calls.some((call) => call.session.id === selectedId.value)
  if (!valid) {
    const first = store.calls[0]
    if (!first) return
    void router.replace({ query: { call: first.session.id } })
  }
})

const selected = computed(() => store.calls.find((call) => call.session.id === selectedId.value) ?? null)

const description =
  opsDataSource === 'mock'
    ? 'In-progress sessions. Elapsed time advances from started_at. Transcript segments and findings are the latest mock snapshot.'
    : 'In-progress sessions polled from GET /v1/calls. Transcript segments and findings load from GET /v1/calls/{id}.'

function elapsed(startedAt: string): number {
  return Math.max(0, now.value - Date.parse(startedAt))
}

function selectCall(id: string): void {
  void router.replace({ query: { call: id } })
}
</script>

<template>
  <section class="page">
    <PageHeader
      kicker="Live"
      title="Live calls"
      :description="description"
    />
    <div class="toolbar">
      <p class="caption">{{ store.calls.length }} in progress</p>
      <button type="button" @click="store.load()">Refresh snapshot</button>
    </div>
    <LoadError v-if="store.error" :message="store.error" @retry="store.load()" />
    <p v-if="store.loading && !store.loaded" class="empty">Loading live board…</p>
    <p v-else-if="store.loaded && store.calls.length === 0" class="empty">No in-progress calls in this snapshot.</p>
    <div v-else-if="store.loaded" class="live-layout" data-testid="live-board">
      <div class="rail" data-testid="live-call-list">
        <button
          v-for="call in store.calls"
          :key="call.session.id"
          type="button"
          class="rail-card"
          :aria-current="call.session.id === selectedId"
          @click="selectCall(call.session.id)"
        >
          <div class="rail-top">
            <span class="pulse" aria-hidden="true" />
            <span class="mono">{{ formatDuration(elapsed(call.session.started_at)) }}</span>
            <StatusPill :status="call.session.state" />
          </div>
          <p class="rail-number">{{ call.session.caller_number_e164 }}</p>
          <StateTag
            v-if="call.gaps.conversation_state"
            :state="call.gaps.conversation_state"
            :layer="call.gaps.conversation_state_record_layer ?? undefined"
          />
          <p class="rail-class">{{ classificationLabel(call.gaps.classification.label) }}</p>
          <p class="muted">{{ campaignCaption(call.gaps.campaign_id, call.gaps.campaign_label) }}</p>
        </button>
      </div>
      <article v-if="selected" class="stage" data-testid="live-detail">
        <header class="stage-head">
          <div>
            <p v-if="selected.session.external_call_id" class="mono">{{ selected.session.external_call_id }}</p>
            <h2>{{ selected.session.caller_number_e164 }}</h2>
            <div class="inline-tags">
              <StateTag
                v-if="selected.gaps.conversation_state"
                :state="selected.gaps.conversation_state"
                :layer="selected.gaps.conversation_state_record_layer ?? undefined"
              />
              <ClassificationTag :classification="selected.gaps.classification" />
            </div>
          </div>
          <div class="stage-actions">
            <p class="elapsed">{{ formatDuration(elapsed(selected.session.started_at)) }}</p>
            <p class="caption">Elapsed</p>
            <router-link v-if="selected.gaps.campaign_id" :to="`/dashboard/campaigns/${selected.gaps.campaign_id}`">
              {{ campaignCaption(selected.gaps.campaign_id, selected.gaps.campaign_label) }}
            </router-link>
            <router-link :to="`/dashboard/calls/${selected.session.id}`">Open call record</router-link>
          </div>
        </header>
        <LatencyStrip
          v-if="selected.gaps.pipeline"
          :stt-ms="selected.gaps.pipeline.stt_ms"
          :select-ms="selected.gaps.pipeline.select_ms"
          :tts-ms="selected.gaps.pipeline.tts_ms"
          :e2e-ms="selected.gaps.pipeline.e2e_ms"
          :sampled-at="selected.gaps.pipeline.sampled_at"
        />
        <div class="split">
          <section>
            <h2 class="section-label">Transcript</h2>
            <TranscriptLog :turns="selected.transcript" />
          </section>
          <section>
            <h2 class="section-label">Findings</h2>
            <IntelligenceList :items="selected.findings" empty="No findings proposed yet." />
          </section>
        </div>
      </article>
    </div>
  </section>
</template>
