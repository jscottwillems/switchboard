"""Idempotent intelligence build for one transcript."""

from switchboard_intelligence.extraction.attribute import Attributor, NoCampaignCorpusAttributor
from switchboard_intelligence.extraction.deterministic import DeterministicExtractor, dedupe_observations
from switchboard_intelligence.extraction.infer import infer_from_observations
from switchboard_intelligence.extraction.model import ModelExtractor
from switchboard_intelligence.schemas.bundle import IntelligenceBundle
from switchboard_intelligence.schemas.transcript import Transcript


def extract_intelligence(
    transcript: Transcript,
    model_extractor: ModelExtractor | None = None,
    attributor: Attributor | None = None,
) -> IntelligenceBundle:
    """Extract observations, derive rule inferences, and attribute if asked.

    The same transcript always yields the same bundle when the optional
    extractor and attributor are omitted or are themselves deterministic.
    Model extraction is skipped unless `model_extractor` is passed.
    Attribution is skipped unless `attributor` is passed; the default
    corpus-less attributor returns no attributions.
    """
    observations = DeterministicExtractor().extract(transcript)
    if model_extractor is not None:
        extra = model_extractor.extract(transcript, observations)
        observations = dedupe_observations([*observations, *extra])
    inferences = infer_from_observations(transcript.call_id, observations)
    if attributor is None:
        attributor = NoCampaignCorpusAttributor()
    attributions = attributor.attribute(transcript.call_id, observations, inferences)
    return IntelligenceBundle(
        call_id=transcript.call_id,
        observations=observations,
        inferences=inferences,
        attributions=attributions,
        elicited_hints=list(transcript.elicited_hints),
    )
