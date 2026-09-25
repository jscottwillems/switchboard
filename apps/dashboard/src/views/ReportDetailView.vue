<script setup lang="ts">
import JsonFactTree from '@/components/JsonFactTree.vue'
import LoadError from '@/components/LoadError.vue'
import PageHeader from '@/components/PageHeader.vue'
import { defaultReportFormat, isReportFormat, reportFormatLabel, reportKindLabel } from '@/lib/reports'
import { useReportDetailStore } from '@/stores/reports'
import type { ReportPart } from '@/types/reports'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const store = useReportDetailStore()
const selectedFilename = ref('')

const reportId = computed(() => (typeof route.params.reportId === 'string' ? route.params.reportId : ''))
const formatQuery = computed(() => (typeof route.query.format === 'string' ? route.query.format : null))

watch(
  [reportId, formatQuery],
  () => {
    if (!reportId.value) return
    const format = formatQuery.value && isReportFormat(formatQuery.value) ? formatQuery.value : null
    void store.load(reportId.value, format)
  },
  { immediate: true },
)

watch(
  () => store.entry,
  (entry) => {
    if (!entry || entry.report_id !== reportId.value) return
    if (formatQuery.value && isReportFormat(formatQuery.value)) return
    void router.replace({ query: { format: defaultReportFormat(entry.available_formats) } })
  },
)

watch(
  () => store.opened,
  (opened) => {
    selectedFilename.value = opened?.primary_filename ?? ''
  },
)

const part = computed((): ReportPart | null => {
  const opened = store.opened
  if (!opened) return null
  return opened.parts.find((item) => item.filename === selectedFilename.value) ?? opened.parts[0] ?? null
})

const parsedJson = computed((): unknown | null => {
  const current = part.value
  if (!current || !current.content_type.includes('json')) return null
  try {
    return JSON.parse(current.body) as unknown
  } catch {
    return null
  }
})

const jsonBroken = computed(() => {
  const current = part.value
  return Boolean(current && current.content_type.includes('json') && parsedJson.value === null)
})

function onFormat(event: Event): void {
  const value = (event.target as HTMLSelectElement).value
  if (!isReportFormat(value)) return
  void router.replace({ query: { format: value } })
}

function onPart(event: Event): void {
  selectedFilename.value = (event.target as HTMLSelectElement).value
}

function reload(): void {
  const format = formatQuery.value && isReportFormat(formatQuery.value) ? formatQuery.value : null
  if (reportId.value) void store.load(reportId.value, format)
}
</script>

<template>
  <section class="page">
    <p v-if="store.loading && !store.entry" class="empty">Opening {{ reportId }}…</p>
    <LoadError v-else-if="store.error" :message="store.error" @retry="reload" />
    <div v-else-if="store.notFound" class="empty" data-testid="report-missing">
      <h1>Report not in the mock catalog</h1>
      <p>No fixture is loaded for {{ reportId }}.</p>
      <router-link to="/dashboard/reports">Back to reports</router-link>
    </div>
    <template v-else-if="store.entry">
      <PageHeader
        kicker="Clerk report"
        :title="store.entry.title"
        description="Format picker calls the mock open-report. JSON bodies map each CLERK fact class onto an Observed, Inferred, or Unverified badge."
      />
      <div class="detail-head">
        <p class="mono">{{ store.entry.report_id }}</p>
        <p class="muted">{{ reportKindLabel(store.entry.kind) }} · {{ store.entry.package_id }}</p>
        <router-link to="/dashboard/reports">All reports</router-link>
      </div>
      <form class="filters" @submit.prevent>
        <label>
          Format
          <select :value="formatQuery ?? ''" data-testid="report-format" @change="onFormat">
            <option v-for="format in store.entry.available_formats" :key="format" :value="format">
              {{ reportFormatLabel(format) }}
            </option>
          </select>
        </label>
        <label v-if="store.opened && store.opened.parts.length > 1">
          File
          <select :value="selectedFilename" data-testid="report-part" @change="onPart">
            <option v-for="item in store.opened.parts" :key="item.filename" :value="item.filename">
              {{ item.filename }}{{ item.filename === store.opened.primary_filename ? ' (primary)' : '' }}
            </option>
          </select>
        </label>
      </form>
      <p v-if="store.formatUnavailable" class="banner" role="alert" data-testid="report-format-unavailable">
        {{ formatQuery }} is not available for this report. Choose one of
        {{ store.entry.available_formats.join(', ') }}.
      </p>
      <p v-else-if="store.loading" class="caption">Opening format…</p>
      <template v-else-if="store.opened && part">
        <p class="caption">
          {{ part.filename }} · {{ part.content_type }}
          <span v-if="part.filename === store.opened.primary_filename"> · primary</span>
        </p>
        <p v-if="parsedJson !== null" class="caption">
          Fact-class badges are a dashboard reading. The CLERK tag stays next to the badge.
        </p>
        <div v-if="parsedJson !== null" class="json-tree" data-testid="report-json">
          <JsonFactTree :value="parsedJson" />
        </div>
        <p v-else-if="jsonBroken" class="banner" role="alert">This part was labeled JSON but did not parse.</p>
        <pre v-else class="report-body" data-testid="report-text">{{ part.body }}</pre>
      </template>
    </template>
  </section>
</template>
