/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  /** `mock` uses fixtures. Unset or `api` reads GET /v1/calls. */
  readonly VITE_OPS_DATA?: 'api' | 'mock'
  readonly VITE_LIVE_POLL_MS?: string
  /**
   * Sent as `X-Switchboard-Operator-Token` on read-API fetches.
   * Ignored when `VITE_OPS_DATA=mock`. Vite inlines this at build time.
   */
  readonly VITE_OPERATOR_TOKEN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
