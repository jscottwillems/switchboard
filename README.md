# Switchboard

Scam-call honeypot. The first package is LOKI, the conversation policy: what the honeypot says, which goal it is pursuing, and an offline evaluation of that behavior.

Other agents (Sherlock, Echo, Watson, Sentinel) are not implemented in this repository. Contracts they can pick up are in `docs/API_CONTRACTS.md` and `docs/EVENTS.md`.

## Run the offline eval

```bash
python -m switchboard.loki.eval
pytest
```

No phone line and no model API are required. Scenarios live in `switchboard/loki/data/scenarios.json`. The state machine is described in `docs/loki/STATE_MACHINE.md`.
