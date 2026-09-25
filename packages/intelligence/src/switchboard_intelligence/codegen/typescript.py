"""Write TypeScript types from the Pydantic models.

Pydantic is the source of truth. The checked-in file
`packages/intelligence/typescript/intelligence.ts` is a mirror.
Regenerate it with `python -m switchboard_intelligence.codegen.typescript`
and commit the result. Tests fail when the file drifts.
"""

import types
from enum import Enum
from pathlib import Path
from typing import Annotated, Literal, Union, get_args, get_origin

from pydantic import BaseModel

from switchboard_intelligence.schemas.attribution import (
    Attribution,
    AttributionStatus,
    AttributionSubject,
)
from switchboard_intelligence.schemas.bundle import IntelligenceBundle
from switchboard_intelligence.schemas.common import SCHEMA_VERSION
from switchboard_intelligence.schemas.hints import ElicitedHint
from switchboard_intelligence.schemas.inference import Inference, InferenceKind, InferenceMethod
from switchboard_intelligence.schemas.observation import (
    Observation,
    ObservationKind,
    PaymentMethod,
    PretextCategory,
)
from switchboard_intelligence.schemas.transcript import SpeakerRole, Transcript, TranscriptSegment

ENUMS: tuple[type[Enum], ...] = (
    SpeakerRole,
    PretextCategory,
    PaymentMethod,
    ObservationKind,
    InferenceKind,
    InferenceMethod,
    AttributionSubject,
    AttributionStatus,
)

MODELS: tuple[type[BaseModel], ...] = (
    ElicitedHint,
    TranscriptSegment,
    Transcript,
    Observation,
    Inference,
    Attribution,
    IntelligenceBundle,
)

HEADER = """/**
 * Generated from the Sherlock Pydantic models. Do not edit by hand.
 *
 * Source of truth: packages/intelligence/src/switchboard_intelligence/schemas
 * Regenerate: python -m switchboard_intelligence.codegen.typescript
 */
"""


def output_path() -> Path:
    return Path(__file__).resolve().parents[3] / "typescript" / "intelligence.ts"


def render() -> str:
    parts = [HEADER, f'export const SCHEMA_VERSION = "{SCHEMA_VERSION}" as const;\n']
    for enum_type in ENUMS:
        parts.append(_render_enum(enum_type))
    for model in MODELS:
        parts.append(_render_model(model))
    parts.append(
        "export type IntelligenceRecord = Observation | Inference | Attribution;\n"
    )
    return "\n".join(parts)


def main() -> None:
    path = output_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(), encoding="utf-8")


def _render_enum(enum_type: type[Enum]) -> str:
    values = ",\n".join(f'  "{member.value}"' for member in enum_type)
    return (
        f"export const {enum_type.__name__} = [\n{values},\n] as const;\n\n"
        f"export type {enum_type.__name__} = (typeof {enum_type.__name__})[number];\n"
    )


def _render_model(model: type[BaseModel]) -> str:
    lines = [f"export interface {model.__name__} {{"]
    for name, field in model.model_fields.items():
        lines.append(f"  {name}: {_typescript_type(field.annotation)};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _typescript_type(annotation: object) -> str:
    annotation = _unwrap(annotation)
    if annotation is type(None):
        return "null"
    if annotation is str:
        return "string"
    if annotation is int:
        return "number"
    if annotation is float:
        return "number"
    if annotation is bool:
        return "boolean"
    origin = get_origin(annotation)
    if origin is Literal:
        return " | ".join(_literal_member(arg) for arg in get_args(annotation))
    if origin in (list,):
        inner = _typescript_type(get_args(annotation)[0])
        return f"{inner}[]"
    if origin in (Union, types.UnionType):
        return " | ".join(_typescript_type(arg) for arg in get_args(annotation))
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation.__name__
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation.__name__
    raise TypeError(f"unsupported annotation for TypeScript export: {annotation!r}")


def _unwrap(annotation: object) -> object:
    if get_origin(annotation) is Annotated:
        return _unwrap(get_args(annotation)[0])
    return annotation


def _literal_member(value: object) -> str:
    if isinstance(value, str):
        return f'"{value}"'
    raise TypeError(f"unsupported literal member: {value!r}")


if __name__ == "__main__":
    main()
