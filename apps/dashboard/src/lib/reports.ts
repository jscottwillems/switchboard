import { assertNever } from '@/lib/assertNever'
import type { Provenance } from '@/types/models'
import {
  FACT_CLASSES,
  REPORT_FORMATS,
  type FactClass,
  type ReportFormat,
  type ReportKind,
} from '@/types/reports'

export function isReportFormat(value: string): value is ReportFormat {
  return (REPORT_FORMATS as readonly string[]).includes(value)
}

export function isFactClass(value: string): value is FactClass {
  return (FACT_CLASSES as readonly string[]).includes(value)
}

/**
 * Dashboard reading of a CLERK fact class. The fact-class string stays on screen.
 * This does not rewrite the package.
 */
export function factClassProvenance(factClass: FactClass): Provenance {
  switch (factClass) {
    case 'confirmed_observation':
    case 'spoken_identifier':
      return 'observed'
    case 'derived_interpretation':
    case 'derived_association':
      return 'inferred'
    case 'reported_caller_metadata':
    case 'raw_observation':
      return 'unverified'
    default:
      return assertNever(factClass)
  }
}

export function factClassLabel(factClass: FactClass): string {
  switch (factClass) {
    case 'reported_caller_metadata':
      return 'Reported caller metadata'
    case 'spoken_identifier':
      return 'Spoken identifier'
    case 'raw_observation':
      return 'Raw observation'
    case 'confirmed_observation':
      return 'Confirmed observation'
    case 'derived_interpretation':
      return 'Derived interpretation'
    case 'derived_association':
      return 'Derived association'
    default:
      return assertNever(factClass)
  }
}

export function reportFormatLabel(format: ReportFormat): string {
  switch (format) {
    case 'json':
      return 'JSON'
    case 'markdown':
      return 'Markdown'
    case 'pdf_ready':
      return 'PDF-ready'
    case 'csv':
      return 'CSV'
    case 'campaign_summary':
      return 'Campaign summary'
    default:
      return assertNever(format)
  }
}

export function reportKindLabel(kind: ReportKind): string {
  switch (kind) {
    case 'single_call':
      return 'Single call'
    case 'multi_call_campaign':
      return 'Multi-call campaign'
    case 'technical_incident':
      return 'Technical incident'
    case 'machine_readable_json':
      return 'Machine-readable JSON'
    default:
      return assertNever(kind)
  }
}

/** Same primary-file rule as CLERK `primary_filename`. */
export function primaryFilename(reportId: string, format: ReportFormat): string {
  switch (format) {
    case 'json':
      return `${reportId}.json`
    case 'markdown':
      return `${reportId}.md`
    case 'pdf_ready':
      return `${reportId}.html`
    case 'csv':
      return 'calls.csv'
    case 'campaign_summary':
      return `${reportId}.campaign_summary.json`
    default:
      return assertNever(format)
  }
}

export function defaultReportFormat(formats: readonly ReportFormat[]): ReportFormat {
  if (formats.includes('markdown')) return 'markdown'
  const first = formats[0]
  if (!first) throw new Error('report has no formats')
  return first
}
