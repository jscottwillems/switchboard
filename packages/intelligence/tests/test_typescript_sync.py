"""The checked-in TypeScript mirror must match the Pydantic models."""

from pathlib import Path

from switchboard_intelligence.codegen.typescript import render

TYPESCRIPT_PATH = Path(__file__).resolve().parents[1] / "typescript" / "intelligence.ts"


def test_typescript_file_matches_codegen() -> None:
    generated = render()
    checked_in = TYPESCRIPT_PATH.read_text(encoding="utf-8")
    assert checked_in == generated
    assert "claimed_company" in checked_in
    assert 'record_type: "observation"' in checked_in
    assert 'record_type: "inference"' in checked_in
    assert 'record_type: "attribution"' in checked_in
