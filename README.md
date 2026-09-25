# switchboard

## ECHO speech slice

Offline path: sample call audio → mock streaming STT → fixed reply → mock TTS.

From the repo root:

```bash
npm install
npm test
npm run sample
```

`npm run sample` writes `artifacts/sample_call_response.wav` and `artifacts/sample_call_metrics.json`.

Media requirements for BELL are in `docs/API_CONTRACTS.md`. Current handoff is in `docs/STATUS.md`.
