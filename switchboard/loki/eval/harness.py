"""Replay synthetic calls and score them against committed trajectories.

No model API and no telephone network are used. The system prompt is checked
statically. The deterministic policy is the reference speaker.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from switchboard.loki.policy import LokiPolicy
from switchboard.loki.prompt import prompt_contract_failures
from switchboard.loki.safety import spoken_text_issues
from switchboard.loki.states import ConversationState

_SCENARIO_PATH = Path(__file__).resolve().parent.parent / "data" / "scenarios.json"


class ExpectedTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: ConversationState
    state_transition: str
    goals_completed: list[str]
    goals_remaining: list[str]
    response_text: str


class ScenarioTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caller: str
    expected: ExpectedTurn


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    scam_type: str
    summary: str
    turns: list[ScenarioTurn] = Field(min_length=1)


@dataclass
class ScenarioResult:
    scenario_id: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    states: list[str] = field(default_factory=list)
    goals_completed: list[str] = field(default_factory=list)


@dataclass
class EvalReport:
    prompt_failures: list[str]
    results: list[ScenarioResult]

    @property
    def scenarios_passed(self) -> int:
        return sum(1 for result in self.results if result.passed)

    @property
    def scenarios_failed(self) -> int:
        return len(self.results) - self.scenarios_passed

    @property
    def ok(self) -> bool:
        return not self.prompt_failures and self.scenarios_failed == 0 and len(self.results) == 20

    @property
    def states_covered(self) -> list[str]:
        seen: list[str] = []
        for result in self.results:
            for state in result.states:
                if state not in seen:
                    seen.append(state)
        return seen


def load_scenarios(path: Path | None = None) -> list[Scenario]:
    raw = (path or _SCENARIO_PATH).read_text(encoding="utf-8")
    return [Scenario.model_validate(item) for item in _load_json(raw)]


def _load_json(raw: str) -> list[object]:
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("scenarios.json must be a list")
    return data


def evaluate_scenario(scenario: Scenario, policy: LokiPolicy | None = None) -> ScenarioResult:
    runner = policy or LokiPolicy()
    session = runner.start_session(scenario.id)
    failures: list[str] = []
    states: list[str] = []
    for index, spec in enumerate(scenario.turns):
        actual = runner.step(session, spec.caller)
        states.append(actual.state.value)
        prefix = f"turn {index}"
        expected = spec.expected
        if actual.state != expected.state:
            failures.append(f"{prefix} state {actual.state.value} != {expected.state.value}")
        if actual.state_transition != expected.state_transition:
            failures.append(
                f"{prefix} transition {actual.state_transition} != {expected.state_transition}"
            )
        if actual.goals_completed != expected.goals_completed:
            failures.append(
                f"{prefix} goals_completed {actual.goals_completed} != {expected.goals_completed}"
            )
        if actual.goals_remaining != expected.goals_remaining:
            failures.append(
                f"{prefix} goals_remaining {actual.goals_remaining} != {expected.goals_remaining}"
            )
        if actual.response_text != expected.response_text:
            failures.append(
                f"{prefix} response_text {actual.response_text!r} != {expected.response_text!r}"
            )
        for issue in spoken_text_issues(actual.response_text):
            failures.append(f"{prefix} safety: {issue}")
        if actual.state is ConversationState.TERMINATION:
            if "?" in actual.response_text:
                failures.append(f"{prefix} termination asks a question")
        elif "?" not in actual.response_text:
            failures.append(f"{prefix} spoken turn has no question")
        if not actual.reason.strip():
            failures.append(f"{prefix} reason is empty")
    if session.raw_observations[-1].text != scenario.turns[-1].caller:
        failures.append("raw observation was not stored verbatim")
    goals = list(session.goals_completed)
    return ScenarioResult(
        scenario_id=scenario.id,
        passed=not failures,
        failures=failures,
        states=states,
        goals_completed=goals,
    )


def run_evaluation(path: Path | None = None) -> EvalReport:
    scenarios = load_scenarios(path)
    results = [evaluate_scenario(scenario) for scenario in scenarios]
    return EvalReport(prompt_failures=prompt_contract_failures(), results=results)


def format_report(report: EvalReport) -> str:
    lines = ["LOKI offline evaluation", ""]
    if report.prompt_failures:
        lines.append("prompt contract: FAIL")
        lines.extend(f"  - {failure}" for failure in report.prompt_failures)
    else:
        lines.append("prompt contract: PASS")
    lines.append(
        f"scenarios: {report.scenarios_passed}/{len(report.results)} passed"
    )
    lines.append("states covered: " + ", ".join(report.states_covered))
    for result in report.results:
        status = "PASS" if result.passed else "FAIL"
        goals = ",".join(result.goals_completed) or "-"
        lines.append(f"  [{status}] {result.scenario_id} goals={goals}")
        for failure in result.failures:
            lines.append(f"      {failure}")
    lines.append("result: PASS" if report.ok else "result: FAIL")
    lines.append("")
    return "\n".join(lines)
