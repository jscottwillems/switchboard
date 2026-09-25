"""CLI entry points used to run the scorer locally."""

from watson.cli import main


def test_evaluate_writes_a_report(tmp_path) -> None:
    target = tmp_path / "EVALUATION.md"
    assert main(["evaluate", "--report", str(target)]) == 0
    text = target.read_text(encoding="utf-8")
    assert text.startswith("# WATSON deterministic scorer evaluation")
    assert "| operating_point | 11 | 0 | 0 | 94 | 1.000 | 1.000 |" in text


def test_run_prints_explainable_associations(capsys) -> None:
    assert main(["run"]) == 0
    output = capsys.readouterr().out
    assert "irs-2" in output
    assert "decision=associate" in output
    assert "opening_script score" in output
    assert "irs-4" in output
    assert "tech-3" in output
