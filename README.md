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

ECHO's draft media requirements are in `docs/echo/MEDIA_REQUIREMENTS.md`. Shared contract docs are owned by ATLAS and are not part of this slice.
