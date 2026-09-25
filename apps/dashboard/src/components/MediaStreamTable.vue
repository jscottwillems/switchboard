<script setup lang="ts">
import ProvenanceBadge from '@/components/ProvenanceBadge.vue'
import { formatTimestamp } from '@/lib/format'
import type { MediaStream } from '@/types/models'

defineProps<{ streams: MediaStream[] }>()
</script>

<template>
  <div>
    <p class="caption">Media streams are observations. This read does not include audio bytes.</p>
    <div v-if="streams.length" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Stream</th>
            <th>Protocol</th>
            <th>Encoding</th>
            <th>State</th>
            <th>Started</th>
            <th>Ended</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="stream in streams" :key="stream.id">
            <td class="mono">{{ stream.external_stream_id }}</td>
            <td class="mono">{{ stream.protocol }}</td>
            <td class="mono">{{ stream.encoding }} · {{ stream.sample_rate_hz }} Hz</td>
            <td>
              <ProvenanceBadge layer="observation" />
              {{ stream.state }}
            </td>
            <td>{{ formatTimestamp(stream.started_at) }}</td>
            <td>{{ stream.ended_at ? formatTimestamp(stream.ended_at) : 'Open' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="empty">No media streams for this call.</p>
  </div>
</template>
