"""SENTINEL resource limits and adversarial fixtures.

Webhook verification for the skeleton lives in ``switchboard_telephony.MockSignatureVerifier``.
This package does not define a second signature scheme.
"""

from __future__ import annotations

from sentinel.limits import ResourceLimits

__version__ = "0.0.1"

__all__ = ["ResourceLimits", "__version__"]
