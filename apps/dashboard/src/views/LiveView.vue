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
import { formatDuration } from '@/lib/format'
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
  const valid = selectedId.value !== null && store.calls.some((call) => call.id === selectedId.value)
  if (!valid) {
    const first = store.calls[0]
    if (!first) return
    void router.replace({ query: { call: first.id } })
  }
})

const selected = computed(() => store.calls.find((call) => call.id === selectedId.value) ?? null)

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
      description="Calls on the honeypot right now. Elapsed time advances from startedAt. Transcript and intelligence are the latest mock snapshot."
    />
    <div class="toolbar">
      <p class="caption">{{ store.calls.length }} active</p>
      <button type="button" @click="store.load()">Refresh snapshot</button>
    </div>
    <LoadError v-if="store.error" :message="store.error" @retry="store.load()" />
    <p v-if="store.loading && !store.loaded" class="empty">Loading live board…</p>
    <p v-else-if="store.loaded && store.calls.length === 0" class="empty">No active calls in this snapshot.</p>
    <div v-else-if="store.loaded" class="live-layout" data-testid="live-board">
      <div class="rail" data-testid="live-call-list">
        <button
          v-for="call in store.calls"
          :key="call.id"
          type="button"
          class="rail-card"
          :aria-current="call.id === selectedId"
          @click="selectCall(call.id)"
        >
          <div class="rail-top">
            <span class="pulse" aria-hidden="true" />
            <span class="mono">{{ formatDuration(elapsed(call.startedAt)) }}</span>
            <StatusPill :status="call.status" />
          </div>
          <p class="rail-number">{{ call.callerNumberMasked }}</p>
          <StateTag :state="call.conversationState" :provenance="call.stateProvenance" />
          <p class="rail-class">{{ classificationLabel(call.classification.label) }}</p>
          <p class="muted">{{ call.campaignName ?? 'No campaign' }}</p>
        </button>
      </div>
      <article v-if="selected" class="stage" data-testid="live-detail">
        <header class="stage-head">
          <div>
            <p class="mono">{{ selected.id }}</p>
            <h2>{{ selected.callerNumberMasked }}</h2>
            <div class="inline-tags">
              <StateTag :state="selected.conversationState" :provenance="selected.stateProvenance" />
              <ClassificationTag :classification="selected.classification" />
            </div>
          </div>
          <div class="stage-actions">
            <p class="elapsed">{{ formatDuration(elapsed(selected.startedAt)) }}</p>
            <p class="caption">Elapsed</p>
            <router-link v-if="selected.campaignId" :to="`/dashboard/campaigns/${selected.campaignId}`">
              {{ selected.campaignName }}
            </router-link>
            <router-link :to="`/dashboard/calls/${selected.id}`">Open call record</router-link>
          </div>
        </header>
        <LatencyStrip
          :stt-ms="selected.pipeline.sttMs"
          :llm-ms="selected.pipeline.llmMs"
          :tts-ms="selected.pipeline.ttsMs"
          :e2e-ms="selected.pipeline.e2eMs"
          :sampled-at="selected.pipeline.sampledAt"
        />
        <div class="split">
          <section>
            <h2 class="section-label">Live transcript</h2>
            <TranscriptLog :turns="selected.transcript" />
          </section>
          <section>
            <h2 class="section-label">Extracted intelligence</h2>
            <IntelligenceList :items="selected.intelligence" empty="No intelligence extracted yet." />
          </section>
        </div>
      </article>
    </div>
  </section>
</template>
