import { assertNever } from '@/lib/assertNever'
import type {
  CallState,
  CampaignStatus,
  Classification,
  ConversationState,
  EventType,
  FindingKind,
  FindingStatus,
  ObservationCategory,
  ProviderRole,
  ProviderStatus,
  RecordLayer,
  ServiceName,
  Severity,
  Speaker,
  TranscriptSource,
} from '@/types/models'

export function recordLayerLabel(value: RecordLayer): string {
  switch (value) {
    case 'observation':
      return 'Observation'
    case 'interpretation':
      return 'Interpretation'
    case 'attribution':
      return 'Attribution'
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

export function callStateLabel(value: CallState): string {
  switch (value) {
    case 'ringing':
      return 'Ringing'
    case 'in_progress':
      return 'In progress'
    case 'completed':
      return 'Completed'
    case 'failed':
      return 'Failed'
    default:
      return assertNever(value)
  }
}

export function campaignStatusLabel(value: CampaignStatus): string {
  switch (value) {
    case 'hypothesized':
      return 'Hypothesized'
    case 'corroborated':
      return 'Corroborated'
    case 'closed':
      return 'Closed'
    default:
      return assertNever(value)
  }
}

export function findingKindLabel(value: FindingKind): string {
  switch (value) {
    case 'callback_number':
      return 'Callback number'
    case 'pretext':
      return 'Pretext'
    case 'organization_name':
      return 'Organization'
    case 'payment_method':
      return 'Payment method'
    case 'url':
      return 'URL'
    case 'person_name':
      return 'Person name'
    case 'other':
      return 'Other'
    default:
      return assertNever(value)
  }
}

export function findingStatusLabel(value: FindingStatus): string {
  switch (value) {
    case 'proposed':
      return 'Proposed'
    case 'accepted':
      return 'Accepted'
    case 'rejected':
      return 'Rejected'
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

export function transcriptSourceLabel(value: TranscriptSource): string {
  switch (value) {
    case 'stt':
      return 'STT'
    case 'tts_input':
      return 'TTS input'
    default:
      return assertNever(value)
  }
}

export function eventTypeLabel(value: EventType): string {
  switch (value) {
    case 'telephony.call.received':
      return 'Call received'
    case 'telephony.call.answered':
      return 'Call answered'
    case 'telephony.call.completed':
      return 'Call completed'
    case 'telephony.call.failed':
      return 'Call failed'
    case 'media.stream.started':
      return 'Stream started'
    case 'media.stream.stopped':
      return 'Stream stopped'
    case 'media.stream.failed':
      return 'Stream failed'
    case 'speech.segment.partial':
      return 'Partial segment'
    case 'speech.segment.final':
      return 'Final segment'
    case 'speech.synthesis.requested':
      return 'Synthesis requested'
    case 'speech.synthesis.completed':
      return 'Synthesis completed'
    case 'speech.synthesis.failed':
      return 'Synthesis failed'
    case 'conversation.response.selected':
      return 'Response selected'
    case 'conversation.turn.recorded':
      return 'Turn recorded'
    case 'intelligence.finding.proposed':
      return 'Finding proposed'
    case 'campaign.opened':
      return 'Campaign opened'
    case 'campaign.attribution.proposed':
      return 'Attribution proposed'
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
    case 'selector':
      return 'Selector'
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

export function serviceLabel(value: ServiceName): string {
  switch (value) {
    case 'api':
      return 'API'
    case 'media_gateway':
      return 'Media gateway'
    case 'intelligence':
      return 'Intelligence'
    case 'dashboard':
      return 'Dashboard'
    default:
      return assertNever(value)
  }
}
