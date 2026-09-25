"""HTTP adapter for one-call extraction.

The body is the local transcript adapter, not a shared session API.
"""

from fastapi import FastAPI

from switchboard_intelligence.extraction.pipeline import extract_intelligence
from switchboard_intelligence.schemas.bundle import IntelligenceBundle
from switchboard_intelligence.schemas.transcript import Transcript

app = FastAPI(
    title="Switchboard Sherlock",
    version="0.1.0",
    summary="Turn a transcript into observations and rule inferences.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/intelligence/extract", response_model=IntelligenceBundle)
def extract(transcript: Transcript) -> IntelligenceBundle:
    return extract_intelligence(transcript)
