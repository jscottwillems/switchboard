import { opsDataMode } from '@/data/apiConfig'
import { createHttpOpsDataPort } from '@/data/httpPort'
import type { OpsDataPort } from '@/data/port'
import { mockOpsDataPort } from '@/mocks/mockAdapter'

/**
 * Stores talk only to OpsDataPort.
 * `VITE_OPS_DATA=mock` keeps fixtures for offline UI work and does not send a token.
 * Any other value, including unset, reads GET /v1/calls and sends
 * `X-Switchboard-Operator-Token` from `VITE_OPERATOR_TOKEN`.
 */
export const opsDataSource = opsDataMode()

export const opsData: OpsDataPort =
  opsDataSource === 'mock' ? mockOpsDataPort : createHttpOpsDataPort(mockOpsDataPort)
