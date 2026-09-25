"""Labeled synthetic-dataset records and the loader used by evaluation."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from watson.models import CompletedCall
from watson.sherlock.mock import FixtureIntelligenceProvider
from watson.sherlock.models import IntelligenceObservation


class ScenarioTag(str, Enum):
    """Ground-truth situation tags. A call may carry more than one."""

    CLEARLY_RELATED = "clearly_related"
    UNRELATED = "unrelated"
    PARTIAL_OVERLAP = "partial_overlap"
    REPEAT_CALLER = "repeat_caller"
    CHANGING_IDENTIFIERS = "changing_identifiers"


class DatasetCallRecord(BaseModel):
    """One labeled call plus the fixture indicators WATSON will consume."""

    model_config = ConfigDict(extra="forbid")

    call_id: str = Field(min_length=1)
    started_at: datetime
    ended_at: datetime
    caller_id: str | None = None
    transcript: str
    transferred: bool = False
    ivr_path: list[str] = Field(default_factory=list)
    ground_truth_campaign_id: str = Field(min_length=1)
    scenario_tags: list[ScenarioTag] = Field(min_length=1)
    observations: list[IntelligenceObservation]

    def to_call(self) -> CompletedCall:
        return CompletedCall(
            call_id=self.call_id,
            started_at=self.started_at,
            ended_at=self.ended_at,
            caller_id=self.caller_id,
            transcript=self.transcript,
            transferred=self.transferred,
            ivr_path=list(self.ivr_path),
        )


class SyntheticDataset(BaseModel):
    """Versioned labeled dataset. Campaign ids are ground truth, not predictions."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    description: str
    calls: list[DatasetCallRecord] = Field(min_length=1)


def default_dataset_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "synthetic" / "dataset.json"


def default_report_path() -> Path:
    return Path(__file__).resolve().parents[1] / "docs" / "watson" / "EVALUATION.md"


def load_dataset(path: Path | None = None) -> SyntheticDataset:
    target = path or default_dataset_path()
    return SyntheticDataset.model_validate_json(target.read_text(encoding="utf-8"))


def chronological(dataset: SyntheticDataset) -> list[DatasetCallRecord]:
    return sorted(dataset.calls, key=lambda record: (record.started_at, record.call_id))


@dataclass(frozen=True)
class RunnableDataset:
    """Calls, fixture provider, and ground-truth labels ready for the pipeline."""

    dataset: SyntheticDataset

    def records(self) -> list[DatasetCallRecord]:
        return chronological(self.dataset)

    def calls(self) -> list[CompletedCall]:
        return [record.to_call() for record in self.records()]

    def provider(self) -> FixtureIntelligenceProvider:
        return FixtureIntelligenceProvider(
            {record.call_id: record.observations for record in self.dataset.calls}
        )

    def ground_truth(self) -> dict[str, str]:
        return {
            record.call_id: record.ground_truth_campaign_id for record in self.dataset.calls
        }


def prepare(dataset: SyntheticDataset) -> RunnableDataset:
    return RunnableDataset(dataset=dataset)
