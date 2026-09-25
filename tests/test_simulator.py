"""The local simulator drives a live ASGI server without carrier credentials."""

import asyncio
import hashlib
import subprocess
import sys

from switchboard.simulator.drive import drive_call


def test_simulator_cli(live_base_url: str) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "switchboard.simulator",
            "--base-url",
            live_base_url,
            "--secret",
            "test-secret",
            "--provider-call-id",
            "cli-call",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert '"ok": true' in completed.stdout


def test_concurrent_simulator_calls_are_isolated(live_base_url: str) -> None:
    payload_a = b"\xaa\x01"
    payload_b = b"\xbb\x02\x03"

    async def scenario():
        return await asyncio.gather(
            drive_call(
                base_url=live_base_url,
                secret="test-secret",
                from_number="+15551000001",
                provider_call_id="concurrent-a",
                audio_payload=payload_a,
            ),
            drive_call(
                base_url=live_base_url,
                secret="test-secret",
                from_number="+15551000002",
                provider_call_id="concurrent-b",
                audio_payload=payload_b,
            ),
        )

    first, second = asyncio.run(scenario())
    assert first.ok and second.ok
    assert first.call_id != second.call_id
    assert first.observed_sha256 == hashlib.sha256(payload_a).hexdigest()
    assert second.observed_sha256 == hashlib.sha256(payload_b).hexdigest()
