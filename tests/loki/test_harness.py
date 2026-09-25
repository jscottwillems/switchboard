"""The offline harness scores the committed scenarios."""

from switchboard.loki.eval.harness import format_report, load_scenarios, run_evaluation
from switchboard.loki.states import ConversationState


def test_twenty_scenarios_have_unique_ids() -> None:
    scenarios = load_scenarios()
    assert len(scenarios) == 20
    assert len({scenario.id for scenario in scenarios}) == 20
    assert all(scenario.turns for scenario in scenarios)


def test_offline_evaluation_passes_without_a_model_or_a_phone() -> None:
    report = run_evaluation()
    assert report.ok, format_report(report)
    assert report.prompt_failures == []
    assert report.scenarios_passed == 20
    assert set(report.states_covered) == {state.value for state in ConversationState}
    assert "result: PASS" in format_report(report)
