import type { OpsDataPort } from '@/data/port'
import { mockOpsDataPort } from '@/mocks/mockAdapter'

/**
 * Stores talk only to OpsDataPort.
 * Replace this binding with an HTTP or WebSocket adapter when a backend exists.
 */
export const opsData: OpsDataPort = mockOpsDataPort
