"""Shared fixtures for the telephony slice."""

import asyncio
import socket
import threading
import time
import urllib.request

import pytest
import uvicorn
from fastapi.testclient import TestClient

from switchboard.config import Settings
from switchboard.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        public_base_url="http://test",
        media_ws_base_url="ws://test",
        mock_webhook_secret="test-secret",
        twilio_account_sid="",
        twilio_auth_token="",
        log_level="WARNING",
    )


@pytest.fixture
def app(settings: Settings):
    return create_app(settings)


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def live_base_url() -> str:
    """One local uvicorn process for the simulator CLI."""

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    app = create_app(
        Settings(
            public_base_url=base,
            media_ws_base_url=f"ws://127.0.0.1:{port}",
            mock_webhook_secret="test-secret",
            twilio_account_sid="",
            twilio_auth_token="",
            log_level="WARNING",
        )
    )
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]

    def run() -> None:
        asyncio.run(server.serve())

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=0.2) as response:
                if response.status == 200:
                    break
        except OSError:
            time.sleep(0.05)
    else:
        server.should_exit = True
        thread.join(timeout=2)
        raise RuntimeError("live server did not start")
    yield base
    server.should_exit = True
    thread.join(timeout=5)
