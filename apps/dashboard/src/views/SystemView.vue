<script setup lang="ts">
import LatencyStrip from '@/components/LatencyStrip.vue'
import LoadError from '@/components/LoadError.vue'
import PageHeader from '@/components/PageHeader.vue'
import { formatTimestamp, formatUsd } from '@/lib/format'
import { providerRoleLabel, providerStatusLabel, serviceLabel, severityLabel } from '@/lib/labels'
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
  return cost.stt + cost.tts + cost.selector + cost.telephony
})

const concurrencyFraction = computed(() => {
  const concurrency = health.value?.concurrency
  if (!concurrency || concurrency.capacity <= 0) return 0
  return Math.min(1, concurrency.active_calls / concurrency.capacity)
})
</script>

<template>
  <section class="page" data-testid="system-view">
    <PageHeader
      kicker="System"
      title="System health"
      description="Process rows match HealthResponse. Provider gauges, cost, and concurrency are not in the API contract."
      :show-legend="false"
    />
    <div class="toolbar">
      <p v-if="health" class="caption">Sampled {{ formatTimestamp(health.sampled_at) }}</p>
      <button type="button" @click="store.load()">Refresh snapshot</button>
    </div>
    <LoadError v-if="store.error" :message="store.error" @retry="store.load()" />
    <p v-if="store.loading && !store.loaded" class="empty">Loading system health…</p>
    <template v-else-if="health">
      <section class="section">
        <h2>Processes</h2>
        <p class="caption">HealthResponse.status is ok when the process is up. It does not mean Postgres or Redis is reachable.</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Service</th>
                <th>Status</th>
                <th>Version</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="service in health.services" :key="service.service">
                <td>{{ serviceLabel(service.service) }}</td>
                <td><span class="health" :data-status="service.status">{{ service.status }}</span></td>
                <td class="mono">{{ service.version }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="section">
        <h2>Provider gauges</h2>
        <p class="caption">Not in API_CONTRACTS. Selector replaces the old LLM gauge. The hot path times STT, select, and TTS.</p>
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
                <td class="mono">{{ provider.latency_ms }} ms</td>
                <td>{{ provider.detail }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <div class="split">
        <section class="section">
          <LatencyStrip
            :stt-ms="health.latency.stt_ms"
            :select-ms="health.latency.select_ms"
            :tts-ms="health.latency.tts_ms"
            :e2e-ms="health.latency.e2e_ms"
            :sampled-at="health.sampled_at"
          />
        </section>
        <section class="section">
          <h2>Concurrency</h2>
          <p class="elapsed">{{ health.concurrency.active_calls }} / {{ health.concurrency.capacity }}</p>
          <div class="meter">
            <span :style="{ width: `${concurrencyFraction * 100}%` }" />
          </div>
          <p class="caption">Queue depth {{ health.concurrency.queue_depth }}</p>
        </section>
      </div>

      <section class="section">
        <h2>Cost</h2>
        <p class="caption">{{ health.cost.window_label }} · {{ health.cost.currency }}. Total is summed in the UI. No cost route exists.</p>
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
            <dt>Selector</dt>
            <dd>{{ formatUsd(health.cost.selector) }}</dd>
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
