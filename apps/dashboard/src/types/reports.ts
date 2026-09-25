/**
 * CLERK report shapes copied from docs/schemas on cursor/clerk-evidence-packages-cdef.
 * The dashboard mocks these JSON bodies. It does not define a backend.
 */

export const REPORT_FORMATS = ['json', 'markdown', 'pdf_ready', 'csv', 'campaign_summary'] as const
export type ReportFormat = (typeof REPORT_FORMATS)[number]

export const REPORT_KINDS = [
  'single_call',
  'multi_call_campaign',
  'technical_incident',
  'machine_readable_json',
] as const
export type ReportKind = (typeof REPORT_KINDS)[number]

/**
 * CLERK fact classes. Not in API_CONTRACTS.
 * The dashboard maps them onto RecordLayer for display only.
 */
export const FACT_CLASSES = [
  'reported_caller_metadata',
  'spoken_identifier',
  'raw_observation',
  'confirmed_observation',
  'derived_interpretation',
  'derived_association',
] as const
export type FactClass = (typeof FACT_CLASSES)[number]

export interface ReportIndexEntry {
  report_id: string
  package_id: string
  package_ids: string[]
  kind: ReportKind
  title: string
  synthetic: boolean
  available_formats: ReportFormat[]
}

export interface OpenReportRequest {
  report_id: string
  format: ReportFormat
}

export interface ReportPart {
  filename: string
  content_type: string
  body: string
}

export interface OpenReportResponse {
  report_id: string
  package_id: string
  package_ids: string[]
  kind: ReportKind
  format: ReportFormat
  synthetic: boolean
  primary_filename: string
  parts: ReportPart[]
}

export type OpenReportResult =
  | { status: 'opened'; report: OpenReportResponse }
  | { status: 'not_found'; reportId: string }
  | { status: 'format_unavailable'; reportId: string; format: ReportFormat }
