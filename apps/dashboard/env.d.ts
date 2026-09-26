/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  /** `mock` uses fixtures. Unset or `api` reads GET /v1/calls. */
  readonly VITE_OPS_DATA?: 'api' | 'mock'
  readonly VITE_LIVE_POLL_MS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
