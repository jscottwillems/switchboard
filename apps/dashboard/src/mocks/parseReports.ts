import type { ReportCatalogFixture } from '@/mocks/reportFixtureTypes'
import {
  REPORT_FORMATS,
  REPORT_KINDS,
  type ReportFormat,
  type ReportIndexEntry,
  type ReportKind,
  type ReportPart,
} from '@/types/reports'

function fail(ctx: string, message: string): never {
  throw new Error(`${ctx}: ${message}`)
}

function record(value: unknown, ctx: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) fail(ctx, 'expected an object')
  return value as Record<string, unknown>
}

function array(value: unknown, ctx: string): unknown[] {
  if (!Array.isArray(value)) fail(ctx, 'expected an array')
  return value
}

function text(source: Record<string, unknown>, key: string, ctx: string): string {
  const value = source[key]
  if (typeof value !== 'string' || value.length === 0) fail(ctx, `${key} must be a non-empty string`)
  return value
}

function oneOf<T extends string>(source: Record<string, unknown>, key: string, allowed: readonly T[], ctx: string): T {
  const value = text(source, key, ctx)
  if (!(allowed as readonly string[]).includes(value)) fail(ctx, `${key} has unexpected value ${value}`)
  return value as T
}

function formats(value: unknown, ctx: string): ReportFormat[] {
  const items = array(value, ctx)
  if (items.length === 0) fail(ctx, 'available_formats is empty')
  return items.map((item, index) => {
    if (typeof item !== 'string' || !(REPORT_FORMATS as readonly string[]).includes(item)) {
      fail(ctx, `available_formats[${index}] is invalid`)
    }
    return item as ReportFormat
  })
}

function indexEntry(value: unknown, ctx: string): ReportIndexEntry {
  const source = record(value, ctx)
  const kind = oneOf(source, 'kind', REPORT_KINDS, ctx) as ReportKind
  return {
    report_id: text(source, 'report_id', ctx),
    package_id: text(source, 'package_id', ctx),
    package_ids: array(source.package_ids, `${ctx}.package_ids`).map((item, index) => {
      if (typeof item !== 'string' || item.length === 0) fail(ctx, `package_ids[${index}]`)
      return item
    }),
    kind,
    title: text(source, 'title', ctx),
    synthetic: booleanValue(source, 'synthetic', ctx),
    available_formats: formats(source.available_formats, `${ctx}.available_formats`),
  }
}

function booleanValue(source: Record<string, unknown>, key: string, ctx: string): boolean {
  const value = source[key]
  if (typeof value !== 'boolean') fail(ctx, `${key} must be a boolean`)
  return value
}

function part(value: unknown, ctx: string): ReportPart {
  const source = record(value, ctx)
  return {
    filename: text(source, 'filename', ctx),
    content_type: text(source, 'content_type', ctx),
    body: text(source, 'body', ctx),
  }
}

export function parseReportCatalog(value: unknown): ReportCatalogFixture {
  const source = record(value, 'reportCatalog')
  const index = array(source.index, 'reportCatalog.index').map((item, itemIndex) => indexEntry(item, `reportCatalog.index[${itemIndex}]`))
  const renders = array(source.renders, 'reportCatalog.renders').map((item, itemIndex) => {
    const ctx = `reportCatalog.renders[${itemIndex}]`
    const render = record(item, ctx)
    const parts = array(render.parts, `${ctx}.parts`).map((entry, partIndex) => part(entry, `${ctx}.parts[${partIndex}]`))
    if (parts.length === 0) fail(ctx, 'parts is empty')
    return {
      report_id: text(render, 'report_id', ctx),
      format: oneOf(render, 'format', REPORT_FORMATS, ctx),
      parts,
    }
  })
  return { index, renders }
}
