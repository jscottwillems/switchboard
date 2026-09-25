"""WATSON campaign association for Project Switchboard.

Deterministic, explainable scoring. This package does not implement
SHERLOCK, the shared event bus, or the platform data model.
"""

import sys
from pathlib import Path

# `packages/schemas` is the canonical contract tree (SB-009). Prefer an
# installed `switchboard_schemas`, and fall back to the in-repo package.
_SCHEMAS = Path(__file__).resolve().parents[1] / "packages" / "schemas"
if _SCHEMAS.is_dir():
    _entry = str(_SCHEMAS)
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

__version__ = "0.1.0"
