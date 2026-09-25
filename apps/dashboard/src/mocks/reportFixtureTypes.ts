import type { ReportFormat, ReportIndexEntry, ReportPart } from '@/types/reports'

/** Mock file shape. OpenReportResponse is assembled by the adapter. */
export interface ReportRenderFixture {
  report_id: string
  format: ReportFormat
  parts: ReportPart[]
}

export interface ReportCatalogFixture {
  index: ReportIndexEntry[]
  renders: ReportRenderFixture[]
}
