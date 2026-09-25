import { assertNever } from '@/lib/assertNever'
import type {
  CallStatus,
  CampaignStatus,
  Classification,
  ConversationState,
  IntelligenceBasis,
  IntelligenceKind,
  ObservationCategory,
  Provenance,
  ProviderRole,
  ProviderStatus,
  Severity,
  Speaker,
  TechnicalSource,
  TimelineKind,
} from '@/types/models'

export function provenanceLabel(value: Provenance): string {
  switch (value) {
    case 'observed':
      return 'Observed'
    case 'inferred':
      return 'Inferred'
    case 'unverified':
      return 'Unverified'
    default:
      return assertNever(value)
  }
}

export function basisLabel(value: IntelligenceBasis): string {
  switch (value) {
    case 'raw':
      return 'Raw'
    case 'derived':
      return 'Derived'
    default:
      return assertNever(value)
  }
}

export function classificationLabel(value: Classification): string {
  switch (value) {
    case 'irs_impersonation':
      return 'IRS impersonation'
    case 'tech_support':
      return 'Tech support'
    case 'bank_fraud':
      return 'Bank fraud'
    case 'romance':
      return 'Romance'
    case 'utility_shutoff':
      return 'Utility shutoff'
    case 'unknown':
      return 'Unknown'
    default:
      return assertNever(value)
  }
}

export function conversationStateLabel(value: ConversationState): string {
  switch (value) {
    case 'ringing':
      return 'Ringing'
    case 'greeting':
      return 'Greeting'
    case 'identity_probe':
      return 'Identity probe'
    case 'pretext':
      return 'Pretext'
    case 'urgency':
      return 'Urgency'
    case 'payment_request':
      return 'Payment request'
    case 'compliance_stall':
      return 'Compliance stall'
    case 'extraction':
      return 'Extraction'
    case 'closing':
      return 'Closing'
    case 'ended':
      return 'Ended'
    default:
      return assertNever(value)
  }
}

export function callStatusLabel(value: CallStatus): string {
  switch (value) {
    case 'active':
      return 'Active'
    case 'completed':
      return 'Completed'
    case 'abandoned':
      return 'Abandoned'
    case 'error':
      return 'Error'
    default:
      return assertNever(value)
  }
}

export function campaignStatusLabel(value: CampaignStatus): string {
  switch (value) {
    case 'active':
      return 'Active'
    case 'watching':
      return 'Watching'
    case 'closed':
      return 'Closed'
    default:
      return assertNever(value)
  }
}

export function intelligenceKindLabel(value: IntelligenceKind): string {
  switch (value) {
    case 'indicator':
      return 'Indicator'
    case 'entity':
      return 'Entity'
    case 'script_phrase':
      return 'Script phrase'
    case 'tactic':
      return 'Tactic'
    case 'amount':
      return 'Amount'
    case 'callback':
      return 'Callback'
    default:
      return assertNever(value)
  }
}

export function observationCategoryLabel(value: ObservationCategory): string {
  switch (value) {
    case 'payment':
      return 'Payment'
    case 'identity':
      return 'Identity'
    case 'threat':
      return 'Threat'
    case 'tooling':
      return 'Tooling'
    case 'script':
      return 'Script'
    case 'callback':
      return 'Callback'
    case 'other':
      return 'Other'
    default:
      return assertNever(value)
  }
}

export function speakerLabel(value: Speaker): string {
  switch (value) {
    case 'caller':
      return 'Caller'
    case 'honeypot':
      return 'Honeypot'
    default:
      return assertNever(value)
  }
}

export function timelineKindLabel(value: TimelineKind): string {
  switch (value) {
    case 'telephony':
      return 'Telephony'
    case 'state':
      return 'State'
    case 'intel':
      return 'Intel'
    case 'transcript':
      return 'Transcript'
    case 'error':
      return 'Error'
    default:
      return assertNever(value)
  }
}

export function technicalSourceLabel(value: TechnicalSource): string {
  switch (value) {
    case 'telephony':
      return 'Telephony'
    case 'stt':
      return 'STT'
    case 'tts':
      return 'TTS'
    case 'llm':
      return 'LLM'
    case 'orchestrator':
      return 'Orchestrator'
    default:
      return assertNever(value)
  }
}

export function severityLabel(value: Severity): string {
  switch (value) {
    case 'info':
      return 'Info'
    case 'warn':
      return 'Warn'
    case 'error':
      return 'Error'
    default:
      return assertNever(value)
  }
}

export function providerRoleLabel(value: ProviderRole): string {
  switch (value) {
    case 'telephony':
      return 'Telephony'
    case 'stt':
      return 'STT'
    case 'tts':
      return 'TTS'
    case 'llm':
      return 'LLM'
    default:
      return assertNever(value)
  }
}

export function providerStatusLabel(value: ProviderStatus): string {
  switch (value) {
    case 'ok':
      return 'OK'
    case 'degraded':
      return 'Degraded'
    case 'down':
      return 'Down'
    default:
      return assertNever(value)
  }
}
