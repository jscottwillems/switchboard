<script setup lang="ts">
import LatencyStrip from '@/components/LatencyStrip.vue'
import LoadError from '@/components/LoadError.vue'
import PageHeader from '@/components/PageHeader.vue'
import { formatTimestamp, formatUsd } from '@/lib/format'
import { providerRoleLabel, providerStatusLabel, severityLabel } from '@/lib/labels'
import { useSystemStore } from '@/stores/system'
import { computed, onMounted } from 'vue'

const store = useSystemStore()

onMounted(() => {
  void store.load()
})

const health = computed(() => store.health)

const costTotal = computed(() => {
  const cost = health.value?.cost
  if (!cost) return 0
  return cost.stt + cost.tts + cost.llm + cost.telephony
})

const concurrencyFraction = computed(() => {
  const concurrency = health.value?.concurrency
  if (!concurrency || concurrency.capacity <= 0) return 0
  return Math.min(1, concurrency.activeCalls / concurrency.capacity)
})
</script>

<template>
  <section class="page" data-testid="system-view">
    <PageHeader
      kicker="System"
      title="System health"
      description="Provider status, pipeline latency, concurrency, cost, and recent errors."
      :show-legend="false"
    />
    <div class="toolbar">
      <p v-if="health" class="caption">Sampled {{ formatTimestamp(health.sampledAt) }}</p>
      <button type="button" @click="store.load()">Refresh snapshot</button>
    </div>
    <LoadError v-if="store.error" :message="store.error" @retry="store.load()" />
    <p v-if="store.loading && !store.loaded" class="empty">Loading system health…</p>
    <template v-else-if="health">
      <section class="section">
        <h2>Providers</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Provider</th>
                <th>Role</th>
                <th>Status</th>
                <th>Latency</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="provider in health.providers" :key="provider.id">
                <td>{{ provider.name }}</td>
                <td>{{ providerRoleLabel(provider.role) }}</td>
                <td>
                  <span class="health" :data-status="provider.status">{{ providerStatusLabel(provider.status) }}</span>
                </td>
                <td class="mono">{{ provider.latencyMs }} ms</td>
                <td>{{ provider.detail }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <div class="split">
        <section class="section">
          <LatencyStrip
            :stt-ms="health.latency.sttMs"
            :llm-ms="health.latency.llmMs"
            :tts-ms="health.latency.ttsMs"
            :e2e-ms="health.latency.e2eMs"
            :sampled-at="health.sampledAt"
          />
        </section>
        <section class="section">
          <h2>Concurrency</h2>
          <p class="elapsed">{{ health.concurrency.activeCalls }} / {{ health.concurrency.capacity }}</p>
          <div class="meter">
            <span :style="{ width: `${concurrencyFraction * 100}%` }" />
          </div>
          <p class="caption">Queue depth {{ health.concurrency.queueDepth }}</p>
        </section>
      </div>

      <section class="section">
        <h2>Cost</h2>
        <p class="caption">{{ health.cost.windowLabel }} · {{ health.cost.currency }}. Total is summed in the UI.</p>
        <dl class="stats">
          <div>
            <dt>STT</dt>
            <dd>{{ formatUsd(health.cost.stt) }}</dd>
          </div>
          <div>
            <dt>TTS</dt>
            <dd>{{ formatUsd(health.cost.tts) }}</dd>
          </div>
          <div>
            <dt>LLM</dt>
            <dd>{{ formatUsd(health.cost.llm) }}</dd>
          </div>
          <div>
            <dt>Telephony</dt>
            <dd>{{ formatUsd(health.cost.telephony) }}</dd>
          </div>
          <div>
            <dt>Total</dt>
            <dd>{{ formatUsd(costTotal) }}</dd>
          </div>
        </dl>
      </section>

      <section class="section">
        <h2>Errors</h2>
        <ul class="reason-list">
          <li v-for="item in health.errors" :key="item.id" class="reason">
            <div class="intel-top">
              <span class="severity" :data-severity="item.severity">{{ severityLabel(item.severity) }}</span>
              <span class="mono">{{ formatTimestamp(item.at) }}</span>
              <span>{{ item.source }}</span>
            </div>
            <p>{{ item.message }}</p>
          </li>
        </ul>
      </section>
    </template>
  </section>
</template>
