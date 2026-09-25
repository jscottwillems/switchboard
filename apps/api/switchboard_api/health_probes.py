"""TCP liveness for the API health route.

The skeleton does not open database or Redis clients. A successful connect
only means something accepted TCP on that host and port.
"""

from __future__ import annotations

import socket
from urllib.parse import urlparse


def tcp_reachable(url: str, *, timeout: float = 0.2) -> bool:
    """Return True when a TCP connection to the URL's host and port succeeds."""
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port
    if host is None or port is None:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
