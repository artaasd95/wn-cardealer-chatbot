"""Runs every scenario JSON under tests/scenarios/ against the app.

The scenario files are the shared source of truth: ``scripts/run_scenarios.py``
sends them to a live server over HTTP, and this module drives the very same
files through the FastAPI app with the LLM port faked. The optional ``llm``
block of each step is what makes the fake deterministic: it pins the intent,
the extraction and the wording the real provider would produce.

These tests are deliberately not executed together with the live runner in one
go — pick one harness per run (see tests/scenarios/README.md).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from scripts.run_scenarios import (
    DEFAULT_SCENARIOS_DIR,
    Request,
    Response,
    Scenario,
    load_scenarios,
    run_scenario,
)

from models.inputs.car import CarExtraction
from models.inputs.response import ResponseWording
from models.inputs.schedule import ScheduleExtraction
from models.inputs.task import TaskDecision
from tests.fakes import FakeLLM

pytestmark = pytest.mark.integration

SCENARIOS: list[Scenario] = load_scenarios(DEFAULT_SCENARIOS_DIR, suite="all")


def _apply_llm_hints(fake_llm: FakeLLM, hints: dict) -> None:
    """Load one step's scripted LLM answers into the fake.

    Args:
        fake_llm: The scripted LLM port wired into the app.
        hints: The step's ``llm`` block (intent / car / schedule / reply).
    """
    if "intent" in hints:
        fake_llm.enqueue(TaskDecision(task_type=hints["intent"], confidence=0.9, reason="scenario"))
    if "car" in hints:
        fake_llm.enqueue(CarExtraction.model_validate(hints["car"]))
    if "schedule" in hints:
        fake_llm.enqueue(ScheduleExtraction.model_validate(hints["schedule"]))
    if "reply" in hints:
        fake_llm.enqueue(ResponseWording(reply=hints["reply"]))


@pytest.fixture
def scenario_client(build_app, fake_llm: FakeLLM) -> Iterator[tuple[TestClient, FakeLLM]]:
    """App client whose LLM answers exactly what the scenario scripts.

    Args:
        build_app: App factory fixture from tests/integration/api/conftest.py.
        fake_llm: Scripted LLM port.

    Yields:
        Tuple of the connected TestClient and the fake LLM.
    """
    with TestClient(build_app(fake_llm)) as client:
        yield client, fake_llm


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.scenario_id for s in SCENARIOS])
def test_scenario(scenario: Scenario, scenario_client: tuple[TestClient, FakeLLM]) -> None:
    """Run one scenario file, step by step, against the app.

    Args:
        scenario: The scenario under test.
        scenario_client: App client plus its scripted LLM.
    """
    client, fake_llm = scenario_client

    def send(request: Request) -> Response:
        raw = client.request(
            request.method,
            request.path,
            json=request.body if request.body is not None else None,
        )
        try:
            body = raw.json()
        except ValueError:
            body = None
        return Response(status=raw.status_code, body=body)

    result = run_scenario(
        scenario,
        send,
        prepare=lambda step: _apply_llm_hints(fake_llm, step.llm),
    )

    problems: list[str] = []
    if result.error:
        problems.append(result.error)
    for step_result in result.steps:
        problems.extend(f"{step_result.step.name}: {line}" for line in step_result.failures)
        if step_result.response is None:
            problems.append(f"{step_result.step.name}: no response received")

    assert not problems, "\n".join(problems)
