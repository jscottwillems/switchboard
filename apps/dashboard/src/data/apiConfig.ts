/** Read-API settings. Vite inlines `VITE_*` at build time. */

const PRODUCTION_API_BASE = 'http://localhost:8000'
const DEFAULT_POLL_MS = 5000

export type OpsDataMode = 'api' | 'mock'

export function opsDataMode(): OpsDataMode {
  return import.meta.env.VITE_OPS_DATA === 'mock' ? 'mock' : 'api'
}

/**
 * Base URL for `/v1/calls`.
 * Unset during `vite` dev is empty so requests stay same-origin and the dev proxy forwards `/v1`.
 * A configured value, including the production default, is used as an absolute origin.
 */
export function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL
  if (typeof configured === 'string') return configured.replace(/\/$/, '')
  if (import.meta.env.DEV) return ''
  return PRODUCTION_API_BASE
}

export function livePollMs(): number {
  const raw = import.meta.env.VITE_LIVE_POLL_MS
  if (!raw) return DEFAULT_POLL_MS
  const parsed = Number(raw)
  if (!Number.isFinite(parsed) || parsed < 1000) return DEFAULT_POLL_MS
  return parsed
}
