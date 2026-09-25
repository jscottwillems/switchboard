<script setup lang="ts">
import LoadError from '@/components/LoadError.vue'
import PageHeader from '@/components/PageHeader.vue'
import { defaultReportFormat, reportFormatLabel, reportKindLabel } from '@/lib/reports'
import { useReportListStore } from '@/stores/reports'
import { onMounted } from 'vue'

const store = useReportListStore()

onMounted(() => {
  void store.load()
})
</script>

<template>
  <section class="page">
    <PageHeader
      kicker="Clerk"
      title="Evidence reports"
      description="Open a CLERK report package. The list is the mock of GET /clerk/reports."
    />
    <LoadError v-if="store.error" :message="store.error" @retry="store.load()" />
    <p v-if="store.loading && !store.loaded" class="empty">Loading reports…</p>
    <div v-else-if="store.loaded" class="table-wrap" data-testid="report-table">
      <table>
        <thead>
          <tr>
            <th>Report</th>
            <th>Kind</th>
            <th>Package</th>
            <th>Formats</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="report in store.reports" :key="report.report_id">
            <td>
              <router-link :to="{ path: `/dashboard/reports/${report.report_id}`, query: { format: defaultReportFormat(report.available_formats) } }">
                {{ report.title }}
              </router-link>
              <div class="mono muted">{{ report.report_id }}</div>
              <span v-if="report.synthetic" class="status-pill">Synthetic</span>
            </td>
            <td>{{ reportKindLabel(report.kind) }}</td>
            <td class="mono">{{ report.package_id }}</td>
            <td>{{ report.available_formats.map(reportFormatLabel).join(', ') }}</td>
          </tr>
          <tr v-if="store.reports.length === 0">
            <td colspan="4" class="empty">No reports in the mock catalog.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
