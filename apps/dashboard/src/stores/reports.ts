import { opsData } from '@/data/client'
import type { OpenReportResponse, ReportFormat, ReportIndexEntry } from '@/types/reports'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useReportListStore = defineStore('reportList', () => {
  const reports = ref<ReportIndexEntry[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)

  async function load(): Promise<void> {
    if (!loaded.value) loading.value = true
    error.value = null
    try {
      reports.value = await opsData.fetchReportIndex()
      loaded.value = true
    } catch (caught) {
      error.value = caught instanceof Error ? caught.message : 'Failed to load reports'
    } finally {
      loading.value = false
    }
  }

  return { reports, loading, loaded, error, load }
})

export const useReportDetailStore = defineStore('reportDetail', () => {
  const entry = ref<ReportIndexEntry | null>(null)
  const opened = ref<OpenReportResponse | null>(null)
  const loading = ref(false)
  const notFound = ref(false)
  const formatUnavailable = ref(false)
  const error = ref<string | null>(null)
  let ticket = 0

  async function load(reportId: string, format: ReportFormat | null): Promise<void> {
    const mine = ++ticket
    loading.value = true
    notFound.value = false
    formatUnavailable.value = false
    error.value = null
    opened.value = null
    try {
      const index = await opsData.fetchReportIndex()
      if (mine !== ticket) return
      const found = index.find((item) => item.report_id === reportId) ?? null
      entry.value = found
      if (!found) {
        notFound.value = true
        return
      }
      if (!format) return
      const result = await opsData.openReport({ report_id: reportId, format })
      if (mine !== ticket) return
      if (result.status === 'not_found') {
        notFound.value = true
        return
      }
      if (result.status === 'format_unavailable') {
        formatUnavailable.value = true
        return
      }
      opened.value = result.report
    } catch (caught) {
      if (mine !== ticket) return
      error.value = caught instanceof Error ? caught.message : 'Failed to open report'
    } finally {
      if (mine === ticket) loading.value = false
    }
  }

  return { entry, opened, loading, notFound, formatUnavailable, error, load }
})
