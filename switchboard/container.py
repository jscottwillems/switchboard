"""Wire the telephony slice. Routes depend on this container, not on vendors."""

from dataclasses import dataclass

from switchboard.config import Settings
from switchboard.events.bus import EventBus
from switchboard.lifecycle.service import CallLifecycle
from switchboard.lifecycle.store import InMemorySessionStore
from switchboard.media.framing import MediaFramer, SwitchboardMediaFramer, TwilioMediaFramer
from switchboard.media.gateway import MediaGateway
from switchboard.media.pipeline import FixedToneMediaPipeline, MediaPipeline
from switchboard.providers.base import TelephonyProvider
from switchboard.providers.mock import MockTelephonyProvider
from switchboard.providers.twilio import TwilioTelephonyProvider, TwilioTransport
from switchboard.security.verifier import MockWebhookVerifier, TwilioWebhookVerifier, WebhookVerifier
from switchboard.telemetry.sink import MemoryTelemetrySink, TelemetryEventHandler


@dataclass
class Container:
    settings: Settings
    store: InMemorySessionStore
    bus: EventBus
    telemetry: MemoryTelemetrySink
    providers: dict[str, TelephonyProvider]
    verifiers: dict[str, WebhookVerifier]
    lifecycle: CallLifecycle
    framers: dict[str, MediaFramer]
    pipeline: MediaPipeline
    gateway: MediaGateway


def build_container(settings: Settings, *, twilio_transport: TwilioTransport | None = None) -> Container:
    store = InMemorySessionStore()
    telemetry = MemoryTelemetrySink()
    bus = EventBus()
    bus.subscribe(TelemetryEventHandler(telemetry))
    providers: dict[str, TelephonyProvider] = {
        "mock": MockTelephonyProvider(),
        "twilio": TwilioTelephonyProvider(settings, transport=twilio_transport),
    }
    verifiers: dict[str, WebhookVerifier] = {
        "mock": MockWebhookVerifier(settings.mock_webhook_secret),
        "twilio": TwilioWebhookVerifier(settings.twilio_auth_token),
    }
    lifecycle = CallLifecycle(
        settings=settings,
        store=store,
        bus=bus,
        telemetry=telemetry,
        providers=providers,
    )
    framers: dict[str, MediaFramer] = {
        "mock": SwitchboardMediaFramer(),
        "twilio": TwilioMediaFramer(),
    }
    pipeline: MediaPipeline = FixedToneMediaPipeline()
    gateway = MediaGateway(lifecycle=lifecycle, framers=framers, pipeline=pipeline)
    return Container(
        settings=settings,
        store=store,
        bus=bus,
        telemetry=telemetry,
        providers=providers,
        verifiers=verifiers,
        lifecycle=lifecycle,
        framers=framers,
        pipeline=pipeline,
        gateway=gateway,
    )
