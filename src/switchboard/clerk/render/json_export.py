"""JSON renderings."""

from __future__ import annotations

from pydantic import BaseModel

from switchboard.clerk.errors import RenderError
from switchboard.clerk.schemas.evidence import EvidencePackage
from switchboard.clerk.schemas.reports import MachineReadableExport


def dump_model(model: BaseModel) -> str:
    return model.model_dump_json(indent=2) + "\n"


def machine_readable_export(packages: list[EvidencePackage]) -> MachineReadableExport:
    if not packages:
        raise RenderError("machine-readable export requires at least one package")
    first = packages[0]
    return MachineReadableExport(
        synthetic=first.synthetic,
        generated_at=first.generated_at,
        package_ids=[package.package_id for package in packages],
        packages=list(packages),
    )
