#!/usr/bin/env python
"""Scenario runner: send the JSON scenario payloads to the chat API.

Every scenario file under ``tests/scenarios/normal`` and ``tests/scenarios/edge``
carries real HTTP request payloads plus acceptance rules for the response —
including regular expressions for the free-text reply. This script loads them,
builds the requests, sends them and evaluates the acceptance rules.

Usage
-----
    python scripts/run_scenarios.py --list
    python scripts/run_scenarios.py --dry-run
    python scripts/run_scenarios.py --base-url http://127.0.0.1:8000
    python scripts/run_scenarios.py --suite edge --scenario 32_past
    python scripts/run_scenarios.py --json-report report.json

Exit codes
----------
    0  every expectation held
    1  at least one expectation failed
    2  the API could not be reached (or the runner itself failed)

Scenario schema
---------------
See ``tests/scenarios/README.md`` for the full field-by-field reference. The
short version::

    {
      "id": "edge_32_past_date",
      "title": "Past date is rejected",
      "suite": "edge",
      "plan_refs": ["plan.md §3 Schedule: Past date/time"],
      "tags": ["schedule"],
      "steps": [
        {
          "name": "ask for a date that already passed",
          "llm": {"intent": "SCHEDULE_CALL",
                  "schedule": {"date_raw": "2020-01-01", "time_raw": "10am"}},
          "request": {"session_id": "$session", "message": "2020-01-01 at 10am"},
          "expect": {
            "status": 200,
            "body": {
              "workflow_state": {"equals": "AWAITING_DATETIME"},
              "reply": {"all_of": [{"regex": "already passed"}],
                        "must_not": [{"regex": "booked for"}]}
            }
          }
        }
      ]
    }

The optional ``llm`` block is only used when a harness drives the app with a
scripted LLM (the pytest bridge in tests/integration/api/test_scenarios.py);
against a live server the real provider answers instead and the acceptance
rules must still hold.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIOS_DIR = REPO_ROOT / "tests" / "scenarios"
SUITES = ("normal", "edge")

# "$session" in a request body or path is replaced by the session id captured
# from the most recent response of the running scenario.
SESSION_PLACEHOLDER = "$session"

# "$long_message:N" is replaced by a message of exactly N characters, so the
# DTO length boundaries can be exercised without storing 2000 characters in
# the scenario file itself.
LONG_MESSAGE_PREFIX = "$long_message:"

SendFn = Callable[["Request"], "Response"]
PrepareFn = Callable[["Step"], None]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Request:
    """One resolved HTTP request ready to send."""

    method: str
    path: str
    body: dict[str, Any] | None

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-safe view of the request.

        Returns:
            Dict with method, path and body.
        """
        return {"method": self.method, "path": self.path, "body": self.body}


@dataclass
class Response:
    """One HTTP response as the runner sees it."""

    status: int
    body: Any


@dataclass
class Step:
    """One step of a scenario."""

    name: str
    method: str
    path: str
    request: dict[str, Any]
    expect: dict[str, Any]
    llm: dict[str, Any] = field(default_factory=dict)


@dataclass
class Scenario:
    """One scenario file."""

    scenario_id: str
    title: str
    suite: str
    path: Path
    steps: list[Step]
    description: str = ""
    plan_refs: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class StepResult:
    """The outcome of one step."""

    step: Step
    request: Request
    response: Response | None
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Whether every expectation held (and a response arrived)."""
        return self.response is not None and not self.failures


@dataclass
class ScenarioResult:
    """The outcome of one scenario."""

    scenario: Scenario
    steps: list[StepResult] = field(default_factory=list)
    error: str | None = None

    @property
    def passed(self) -> bool:
        """Whether every step passed."""
        return self.error is None and bool(self.steps) and all(s.passed for s in self.steps)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_scenario_file(path: Path) -> Scenario:
    """Parse one scenario JSON file.

    Args:
        path: The scenario file.

    Returns:
        The parsed Scenario.

    Raises:
        ValueError: When required fields are missing.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    for required in ("id", "title", "suite", "steps"):
        if required not in raw:
            raise ValueError(f"{path}: missing required field '{required}'")

    declared_suite = str(raw["suite"])
    suite_from_path = path.parent.name
    if declared_suite not in SUITES:
        raise ValueError(f"{path}: invalid suite {declared_suite!r}; expected one of {SUITES}")
    if suite_from_path in SUITES and declared_suite != suite_from_path:
        raise ValueError(
            f"{path}: suite {declared_suite!r} does not match directory {suite_from_path!r}"
        )

    steps = [
        Step(
            name=step.get("name", f"step {index + 1}"),
            method=str(step.get("method", "POST")).upper(),
            path=step.get("path", "/api/chat"),
            request=step.get("request", {}) or {},
            expect=step.get("expect", {}) or {},
            llm=step.get("llm", {}) or {},
        )
        for index, step in enumerate(raw["steps"])
    ]

    return Scenario(
        scenario_id=raw["id"],
        title=raw["title"],
        suite=raw["suite"],
        path=path,
        steps=steps,
        description=raw.get("description", ""),
        plan_refs=list(raw.get("plan_refs", [])),
        tags=list(raw.get("tags", [])),
        notes=raw.get("notes", ""),
    )


def load_scenarios(
    scenarios_dir: Path = DEFAULT_SCENARIOS_DIR,
    suite: str = "all",
    scenario_filter: str | None = None,
    tags: Sequence[str] | None = None,
) -> list[Scenario]:
    """Load scenario files, ordered by suite then filename.

    Args:
        scenarios_dir: Directory holding the ``normal`` and ``edge`` suites.
        suite: 'normal', 'edge' or 'all'.
        scenario_filter: Optional substring filter on the scenario id.
        tags: Optional tag filter; a scenario matches when it carries any tag.

    Returns:
        The matching scenarios in deterministic order.
    """
    suites = SUITES if suite == "all" else (suite,)
    scenarios: list[Scenario] = []
    seen_ids: dict[str, Path] = {}
    for one_suite in suites:
        suite_dir = scenarios_dir / one_suite
        for path in sorted(suite_dir.glob("*.json")):
            scenario = load_scenario_file(path)
            previous = seen_ids.get(scenario.scenario_id)
            if previous is not None:
                raise ValueError(
                    "duplicate scenario id "
                    f"{scenario.scenario_id!r} in {previous} and {path}"
                )
            seen_ids[scenario.scenario_id] = path
            if scenario_filter and scenario_filter not in scenario.scenario_id:
                continue
            if tags and not set(tags) & set(scenario.tags):
                continue
            scenarios.append(scenario)
    return scenarios


# ---------------------------------------------------------------------------
# Acceptance matchers
# ---------------------------------------------------------------------------


def _regex_search(pattern: str, value: str) -> bool:
    """Case-insensitive regex search (inline flags may override).

    Args:
        pattern: The regex pattern.
        value: The text to search.

    Returns:
        True when the pattern matches somewhere in the value.
    """
    return re.search(pattern, value, re.IGNORECASE) is not None


def evaluate_matcher(matcher: Any, value: Any, path: str) -> list[str]:
    """Evaluate one acceptance matcher against a value.

    A matcher is either a literal (compared with ==) or an object whose keys
    are combined with AND. Supported keys: equals, in, regex, any_of, all_of,
    must_not, min_length, max_length, min_items, max_items, contains_all,
    contains_any, exists.

    Args:
        matcher: The matcher (literal or dict).
        value: The value under test.
        path: Dotted path used in failure messages.

    Returns:
        Human-readable failure lines; empty when the matcher holds.
    """
    if not isinstance(matcher, dict):
        return [] if value == matcher else [f"{path}: expected {matcher!r}, got {value!r}"]

    failures: list[str] = []
    for key, expected in matcher.items():
        if key == "equals":
            if value != expected:
                failures.append(f"{path}: expected {expected!r}, got {value!r}")
        elif key == "in":
            if value not in expected:
                failures.append(f"{path}: {value!r} not in {expected!r}")
        elif key == "regex":
            if not isinstance(value, str) or not _regex_search(expected, value):
                failures.append(f"{path}: {value!r} does not match /{expected}/")
        elif key == "any_of":
            if not any(not evaluate_matcher(sub, value, path) for sub in expected):
                failures.append(
                    f"{path}: {value!r} matches none of the {len(expected)} alternatives"
                )
        elif key == "all_of":
            for sub in expected:
                failures.extend(evaluate_matcher(sub, value, path))
        elif key == "must_not":
            for sub in expected:
                if not evaluate_matcher(sub, value, path):
                    failures.append(f"{path}: {value!r} unexpectedly matches {sub!r}")
        elif key == "min_length":
            if not isinstance(value, str) or len(value) < expected:
                failures.append(
                    f"{path}: length {len(value) if isinstance(value, str) else '?'} < {expected}"
                )
        elif key == "max_length":
            if not isinstance(value, str) or len(value) > expected:
                failures.append(
                    f"{path}: length {len(value) if isinstance(value, str) else '?'} > {expected}"
                )
        elif key == "min_items":
            if not isinstance(value, list) or len(value) < expected:
                failures.append(
                    f"{path}: {len(value) if isinstance(value, list) else '?'} items < {expected}"
                )
        elif key == "max_items":
            if not isinstance(value, list) or len(value) > expected:
                failures.append(
                    f"{path}: {len(value) if isinstance(value, list) else '?'} items > {expected}"
                )
        elif key == "contains_all":
            for pattern in expected:
                if not isinstance(value, list) or not any(
                    isinstance(item, str) and _regex_search(pattern, item) for item in value
                ):
                    failures.append(f"{path}: no item matches /{pattern}/ in {value!r}")
        elif key == "contains_any":
            if not isinstance(value, list) or not any(
                isinstance(item, str) and any(_regex_search(p, item) for p in expected)
                for item in value
            ):
                failures.append(f"{path}: no item matches any of {[str(p) for p in expected]}")
        elif key == "exists":
            if expected is not (value is not None):
                failures.append(f"{path}: exists={expected} but value is {value!r}")
        else:
            failures.append(f"{path}: unknown matcher key '{key}'")
    return failures


def evaluate_expect(expect: dict[str, Any], response: Response) -> list[str]:
    """Evaluate a step's acceptance rules against a response.

    Args:
        expect: The ``expect`` object of the step.
        response: The response under test.

    Returns:
        Human-readable failure lines; empty when every rule holds.
    """
    failures: list[str] = []

    if "status" in expect:
        failures.extend(evaluate_matcher(expect["status"], response.status, "status"))

    body_matchers = expect.get("body", {})
    for field_name, matcher in body_matchers.items():
        if not isinstance(response.body, dict):
            failures.append(
                f"body.{field_name}: response body is not an object ({response.body!r})"
            )
            continue
        value = response.body.get(field_name)
        failures.extend(evaluate_matcher(matcher, value, f"body.{field_name}"))

    return failures


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def _substitute(value: Any, session_id: str | None) -> Any:
    """Recursively replace the placeholders.

    Supported placeholders:
    - "$session": the session id captured from earlier responses
    - "$long_message:N": a message of exactly N 'a' characters

    Args:
        value: Request fragment (dict/list/str/other).
        session_id: The session id captured so far.

    Returns:
        The same shape with placeholders replaced.
    """
    if isinstance(value, dict):
        return {key: _substitute(item, session_id) for key, item in value.items()}
    if isinstance(value, list):
        return [_substitute(item, session_id) for item in value]
    if isinstance(value, str):
        if value.startswith(LONG_MESSAGE_PREFIX):
            length = int(value[len(LONG_MESSAGE_PREFIX) :])
            return "a" * length
        return value.replace(SESSION_PLACEHOLDER, session_id or "")
    return value


def build_request(step: Step, session_id: str | None) -> Request:
    """Resolve one step into a ready-to-send request.

    Args:
        step: The scenario step.
        session_id: Session id captured from earlier responses.

    Returns:
        The resolved Request (placeholders substituted).
    """
    body = _substitute(step.request, session_id) or None
    path = _substitute(step.path, session_id)
    return Request(method=step.method, path=path, body=body if isinstance(body, dict) else None)


def run_scenario(
    scenario: Scenario,
    send: SendFn,
    prepare: PrepareFn | None = None,
) -> ScenarioResult:
    """Run one scenario against a sender.

    Args:
        scenario: The scenario to run.
        send: Callable taking a Request and returning a Response.
        prepare: Optional hook invoked with each Step before it is sent
            (used by the pytest bridge to load the ``llm`` hints).

    Returns:
        The ScenarioResult with one StepResult per step.
    """
    result = ScenarioResult(scenario=scenario)
    session_id: str | None = None

    for step in scenario.steps:
        request = build_request(step, session_id)
        if prepare is not None:
            prepare(step)

        try:
            response = send(request)
        except Exception as exc:  # noqa: BLE001 - report and move on
            result.error = f"send failed: {exc}"
            result.steps.append(
                StepResult(
                    step=step, request=request, response=None, failures=[f"send failed: {exc}"]
                )
            )
            return result

        # Expectations may reference the captured session id ("$session"), so
        # continuity can be asserted with {"equals": "$session"}.
        failures = evaluate_expect(_substitute(step.expect, session_id), response)
        result.steps.append(
            StepResult(step=step, request=request, response=response, failures=failures)
        )

        if isinstance(response.body, dict) and response.body.get("session_id"):
            session_id = str(response.body["session_id"])

    return result


def http_sender(base_url: str, timeout: float) -> SendFn:
    """Build a sender that talks to a live API over HTTP.

    Args:
        base_url: Base URL of the API (e.g. http://127.0.0.1:8000).
        timeout: Per-request timeout in seconds.

    Returns:
        A SendFn performing real HTTP requests.
    """

    def _send(request: Request) -> Response:
        url = base_url.rstrip("/") + request.path
        data = json.dumps(request.body).encode("utf-8") if request.body is not None else None
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        http_request = urllib.request.Request(
            url, data=data, headers=headers, method=request.method
        )

        try:
            with urllib.request.urlopen(http_request, timeout=timeout) as raw:  # noqa: S310
                status = raw.status
                payload = raw.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            status = exc.code
            payload = exc.read().decode("utf-8")

        body: Any
        try:
            body = json.loads(payload) if payload else None
        except json.JSONDecodeError:
            body = payload
        return Response(status=status, body=body)

    return _send


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def scenario_report(result: ScenarioResult, verbose: bool = False) -> str:
    """Render one scenario result as printable lines.

    Args:
        result: The scenario result.
        verbose: Include the resolved request/response payloads.

    Returns:
        Multi-line report text.
    """
    status = "PASS" if result.passed else "FAIL"
    lines = [f"[{status}] {result.scenario.scenario_id} — {result.scenario.title}"]

    if result.error:
        lines.append(f"    error: {result.error}")

    for step_result in result.steps:
        mark = "ok" if step_result.passed else "FAIL"
        response = step_result.response
        code = response.status if response else "no response"
        lines.append(f"    [{mark}] {step_result.step.name} -> {code}")
        for failure in step_result.failures:
            lines.append(f"        {failure}")
        if verbose and response is not None:
            lines.append(f"        request:  {json.dumps(step_result.request.to_json())}")
            lines.append(f"        response: {json.dumps(response.body)}")
    return "\n".join(lines)


def summary_report(results: Iterable[ScenarioResult]) -> str:
    """Render the final summary table.

    Args:
        results: All scenario results.

    Returns:
        Multi-line summary text.
    """
    results = list(results)
    passed = sum(1 for result in results if result.passed)
    failed = [result for result in results if not result.passed]
    lines = [f"\n{passed}/{len(results)} scenarios passed"]
    for result in failed:
        lines.append(f"  FAILED: {result.scenario.scenario_id}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument vector (defaults to sys.argv[1:]).

    Returns:
        The parsed namespace.
    """
    parser = argparse.ArgumentParser(description="Run chat API scenario payloads.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument("--suite", choices=[*SUITES, "all"], default="all", help="Scenario suite")
    parser.add_argument("--scenario", help="Only run scenario ids containing this substring")
    parser.add_argument(
        "--tag", action="append", help="Only run scenarios carrying any of these tags"
    )
    parser.add_argument("--scenarios-dir", type=Path, default=DEFAULT_SCENARIOS_DIR)
    parser.add_argument(
        "--timeout", type=float, default=30.0, help="Per-request timeout in seconds"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print resolved requests, send nothing"
    )
    parser.add_argument("--list", action="store_true", help="List matching scenarios and exit")
    parser.add_argument("--verbose", action="store_true", help="Print requests and responses")
    parser.add_argument(
        "--fail-fast", action="store_true", help="Stop after the first failing scenario"
    )
    parser.add_argument("--json-report", type=Path, help="Write a machine-readable report here")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: Argument vector (defaults to sys.argv[1:]).

    Returns:
        Process exit code (0 pass, 1 failures, 2 unreachable).
    """
    args = parse_args(argv)

    try:
        scenarios = load_scenarios(args.scenarios_dir, args.suite, args.scenario, args.tag)
    except Exception as exc:  # noqa: BLE001
        print(f"could not load scenarios: {exc}", file=sys.stderr)
        return 2

    if not scenarios:
        print("no scenarios matched the filters")
        return 2

    if args.list:
        for scenario in scenarios:
            tags = f" [{', '.join(scenario.tags)}]" if scenario.tags else ""
            print(f"{scenario.suite}/{scenario.scenario_id}{tags} — {scenario.title}")
        return 0

    if args.dry_run:
        for scenario in scenarios:
            print(f"== {scenario.scenario_id} — {scenario.title}")
            for step in scenario.steps:
                request = build_request(step, "<session-id>")
                print(f"   {json.dumps(request.to_json())}")
        print(f"\n{len(scenarios)} scenarios ready to send (dry run)")
        return 0

    send = http_sender(args.base_url, args.timeout)
    results: list[ScenarioResult] = []
    unreachable = False

    for scenario in scenarios:
        result = run_scenario(scenario, send)
        results.append(result)
        print(scenario_report(result, args.verbose))
        if result.error:
            unreachable = True
            break
        if not result.passed and args.fail_fast:
            break

    print(summary_report(results))

    if args.json_report:
        args.json_report.write_text(
            json.dumps(
                {
                    "base_url": args.base_url,
                    "passed": sum(1 for result in results if result.passed),
                    "total": len(results),
                    "scenarios": [
                        {
                            "id": result.scenario.scenario_id,
                            "passed": result.passed,
                            "steps": [
                                {
                                    "name": step.step.name,
                                    "passed": step.passed,
                                    "request": step.request.to_json(),
                                    "status": step.response.status if step.response else None,
                                    "failures": step.failures,
                                }
                                for step in result.steps
                            ],
                        }
                        for result in results
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"wrote {args.json_report}")

    if unreachable:
        return 2
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    if __package__ in (None, ""):  # executed as `python scripts/run_scenarios.py`
        sys.path.insert(0, str(REPO_ROOT))
    raise SystemExit(main())
