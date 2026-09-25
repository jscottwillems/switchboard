"""Errors that cross the HTTP and media boundaries."""


class SwitchboardError(Exception):
    """Base error for expected telephony failures."""


class WebhookVerificationError(SwitchboardError):
    """The webhook signature is missing, malformed, or does not match."""


class ProviderPayloadError(SwitchboardError):
    """The carrier payload cannot be normalized."""


class FrameDecodeError(SwitchboardError):
    """A media-stream frame is not valid for the selected provider."""


class InvalidRequest(SwitchboardError):
    """The operator request is structurally valid JSON but not acceptable."""


class NotFoundError(SwitchboardError):
    """No call session matches the given identifier."""


class InvalidTransition(SwitchboardError):
    """The call lifecycle rejected this state change."""


class ProviderConfigurationError(SwitchboardError):
    """A vendor side effect needs credentials or URLs that are not configured."""


class ProviderError(SwitchboardError):
    """The telephony provider failed while performing a side effect."""


class ProviderSideEffectError(SwitchboardError):
    """A vendor side effect failed after the local session was marked failed."""

    def __init__(self, message: str, call_id: str) -> None:
        super().__init__(message)
        self.call_id = call_id
