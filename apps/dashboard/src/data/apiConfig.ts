/** Read-API settings. Vite inlines `VITE_*` at build time. */

const DEFAULT_POLL_MS = 5000

export type OpsDataMode = 'api' | 'mock'

export function opsDataMode(): OpsDataMode {
  return import.meta.env.VITE_OPS_DATA === 'mock' ? 'mock' : 'api'
}

/**
 * Origin prepended to `/v1/calls`. Empty is same-origin.
 * Dev, preview, and the compose image proxy `/v1` to the API, so a phone
 * does not call `localhost`. Set `VITE_API_BASE_URL` only for a different
 * origin, and list that origin in `SWITCHBOARD_CORS_ORIGINS`.
 */
export function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL
  if (typeof configured !== 'string') return ''
  const trimmed = configured.trim()
  if (trimmed === '') return ''
  return trimmed.replace(/\/$/, '')
}

export function livePollMs(): number {
  const raw = import.meta.env.VITE_LIVE_POLL_MS
  if (!raw) return DEFAULT_POLL_MS
  const parsed = Number(raw)
  if (!Number.isFinite(parsed) || parsed < 1000) return DEFAULT_POLL_MS
  return parsed
}
