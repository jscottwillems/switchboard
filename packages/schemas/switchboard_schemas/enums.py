from enum import StrEnum


class RecordLayer(StrEnum):
    """Stored facts, derived judgments, and campaign linkage stay distinct."""

    OBSERVATION = "observation"
    INTERPRETATION = "interpretation"
    ATTRIBUTION = "attribution"


class CallState(StrEnum):
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class MediaStreamState(StrEnum):
    CONNECTING = "connecting"
    STREAMING = "streaming"
    CLOSED = "closed"
    FAILED = "failed"


class Speaker(StrEnum):
    CALLER = "caller"
    HONEYPOT = "honeypot"


class TranscriptSource(StrEnum):
    STT = "stt"
    TTS_INPUT = "tts_input"


class FindingKind(StrEnum):
    CALLBACK_NUMBER = "callback_number"
    PRETEXT = "pretext"
    ORGANIZATION_NAME = "organization_name"
    PAYMENT_METHOD = "payment_method"
    URL = "url"
    PERSON_NAME = "person_name"
    OTHER = "other"


class FindingStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class CampaignStatus(StrEnum):
    HYPOTHESIZED = "hypothesized"
    CORROBORATED = "corroborated"
    CLOSED = "closed"


class CarrierProvider(StrEnum):
    MOCK = "mock"


class EventType(StrEnum):
    TELEPHONY_CALL_RECEIVED = "telephony.call.received"
    TELEPHONY_CALL_ANSWERED = "telephony.call.answered"
    TELEPHONY_CALL_COMPLETED = "telephony.call.completed"
    TELEPHONY_CALL_FAILED = "telephony.call.failed"
    MEDIA_STREAM_STARTED = "media.stream.started"
    MEDIA_STREAM_STOPPED = "media.stream.stopped"
    MEDIA_STREAM_FAILED = "media.stream.failed"
    SPEECH_SEGMENT_PARTIAL = "speech.segment.partial"
    SPEECH_SEGMENT_FINAL = "speech.segment.final"
    SPEECH_SYNTHESIS_REQUESTED = "speech.synthesis.requested"
    SPEECH_SYNTHESIS_COMPLETED = "speech.synthesis.completed"
    SPEECH_SYNTHESIS_FAILED = "speech.synthesis.failed"
    CONVERSATION_RESPONSE_SELECTED = "conversation.response.selected"
    CONVERSATION_TURN_RECORDED = "conversation.turn.recorded"
    INTELLIGENCE_FINDING_PROPOSED = "intelligence.finding.proposed"
    CAMPAIGN_OPENED = "campaign.opened"
    CAMPAIGN_ATTRIBUTION_PROPOSED = "campaign.attribution.proposed"


class Producer(StrEnum):
    API = "api"
    MEDIA_GATEWAY = "media_gateway"
    INTELLIGENCE = "intelligence"
