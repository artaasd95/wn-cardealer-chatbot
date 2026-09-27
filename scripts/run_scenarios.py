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
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
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
    elapsed_ms: float | None = None

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

    def to_json(self) -> dict[str, Any]:
        """Serialize the result to a dictionary for logging."""
        return {
            "scenario_id": self.scenario.scenario_id,
            "title": self.scenario.title,
            "passed": self.passed,
            "error": self.error,
            "steps": [
                {
                    "name": s.step.name,
                    "request": s.request.to_json(),
                    "response": {
                        "status": s.response.status,
                        "body": s.response.body,
                    }
                    if s.response
                    else None,
                    "failures": s.failures,
                    "elapsed_ms": round(s.elapsed_ms, 1) if s.elapsed_ms is not None else None,
                }
                for s in self.steps
            ],
        }

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
                    f"duplicate scenario id {scenario.scenario_id!r} in {previous} and {path}"
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


def run_step(
    send: SendFn,
    step: Step,
    session_id: str | None,
    prepare: PrepareFn | None = None,
) -> StepResult:
    """Execute a single step of a scenario.

    Args:
        send: Callable that sends a ``Request`` and returns a ``Response``.
        step: The scenario step to execute.
        session_id: Session id captured from earlier responses (``None`` for
            the first step of a fresh session).
        prepare: Optional callback invoked before the request is built, used
            by the pytest bridge to load scripted LLM answers.

    Returns:
        The outcome of this step including failures.
    """
    if prepare is not None:
        prepare(step)

    request = build_request(step, session_id)
    start = time.monotonic()

    try:
        response = send(request)
    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        return StepResult(step, request, None, [str(exc)], elapsed_ms=elapsed_ms)

    elapsed_ms = (time.monotonic() - start) * 1000

    # Substitute $session placeholders in expect before evaluating.
    resolved_expect: dict[str, Any] = _substitute(step.expect, session_id)
    failures = evaluate_expect(resolved_expect, response)
    return StepResult(step, request, response, failures, elapsed_ms=elapsed_ms)


def run_scenario(
    scenario: Scenario,
    send: SendFn,
    prepare: PrepareFn | None = None,
) -> ScenarioResult:
    """Run a full scenario, step by step.

    Args:
        scenario: The loaded scenario.
        send: Callable that sends a ``Request`` and returns a ``Response``.
        prepare: Optional per-step callback (used by the pytest bridge to
            enqueue scripted LLM answers before each request).

    Returns:
        The aggregated result with per-step outcomes.
    """
    step_results: list[StepResult] = []
    session_id: str | None = None

    for step in scenario.steps:
        result = run_step(send, step, session_id, prepare)
        step_results.append(result)

        # Capture session id from the response so later steps can reference it.
        if result.response is not None and isinstance(result.response.body, dict):
            captured = result.response.body.get("session_id")
            if isinstance(captured, str) and captured:
                session_id = captured

        if not result.passed:
            break

    return ScenarioResult(scenario, steps=step_results)


# ---------------------------------------------------------------------------
# HTTP send factory
# ---------------------------------------------------------------------------


def _make_http_send(base_url: str, timeout: float) -> SendFn:
    """Build a ``SendFn`` that sends requests over HTTP with urllib.

    Args:
        base_url: API origin (e.g. ``http://127.0.0.1:8000``).
        timeout: Per-request timeout in seconds.

    Returns:
        A callable matching the ``SendFn`` protocol.
    """

    def send(request: Request) -> Response:
        url = f"{base_url.rstrip('/')}{request.path}"
        data: bytes | None = None
        headers: dict[str, str] = {}
        if request.body is not None:
            data = json.dumps(request.body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method=request.method,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                body: Any = json.loads(raw) if raw.strip() else None
                return Response(status=resp.status, body=body)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                body = raw
            return Response(status=e.code, body=body)
        except urllib.error.URLError as e:
            raise ConnectionError(f"Cannot reach {url}: {e.reason}") from e

    return send


# ---------------------------------------------------------------------------
# Default report path and env helpers
# ---------------------------------------------------------------------------


def _default_report_path() -> Path:
    """Build the default timestamped report path under logs/scenario_runs/.

    Returns:
        Path like ``logs/scenario_runs/run_20260927_143000.json``.
    """
    from datetime import datetime as _dt

    ts = _dt.now().strftime("%Y%m%d_%H%M%S")
    report_dir = REPO_ROOT / "logs" / "scenario_runs"
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir / f"run_{ts}.json"


def _read_env_timeout() -> float:
    """Read APP_REQUEST_TIMEOUT_SECONDS from the environment or .env file.

    The runner does not depend on pydantic-settings, so it reads the value
    directly.  If the variable is not exported, it falls back to parsing
    ``.env`` at the repository root.  Returns 60 when nothing is found.

    Returns:
        The timeout in seconds (minimum 30).
    """
    raw = os.environ.get("APP_REQUEST_TIMEOUT_SECONDS")
    if raw is None:
        env_path = REPO_ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("APP_REQUEST_TIMEOUT_SECONDS="):
                    raw = stripped.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if raw is None:
        return 60.0
    try:
        return max(30.0, float(raw))
    except ValueError:
        return 60.0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the scenario runner CLI."""
    # Ensure UTF-8 output so Unicode in scenario titles prints on Windows.
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Run chatbot scenarios against a live API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit codes:  0 = all passed,  1 = failures,  2 = API unreachable\n\n"
            "The timeout defaults to APP_REQUEST_TIMEOUT_SECONDS from .env (min 30s)."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("API_BASE_URL", "http://127.0.0.1:8000"),
        help="Base URL of the API (default: API_BASE_URL env or http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--suite",
        choices=["normal", "edge", "all"],
        default="all",
        help="Which scenario suite to run",
    )
    parser.add_argument(
        "--scenario",
        help="Substring filter on scenario id",
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Only run scenarios carrying at least one of these tags (repeatable)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available scenarios and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve requests and print them without sending",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print every request and response during the run",
    )
    parser.add_argument(
        "--json-report",
        help="Write full JSON report to this path (default: logs/scenario_runs/<timestamp>.json)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="HTTP request timeout in seconds (default: APP_REQUEST_TIMEOUT_SECONDS from .env)",
    )

    args = parser.parse_args()

    tags: Sequence[str] | None = args.tag or None
    scenarios = load_scenarios(
        suite=args.suite,
        scenario_filter=args.scenario,
        tags=tags,
    )

    # --list: print scenario inventory and exit.
    if args.list:
        if not scenarios:
            print("No scenarios matched.")
            sys.exit(0)
        for s in scenarios:
            print(f"  {s.scenario_id:<50} {len(s.steps)} steps  [{s.title}]")
        print(f"\n{len(scenarios)} scenario(s).")
        sys.exit(0)

    if not scenarios:
        print("No scenarios matched.", file=sys.stderr)
        sys.exit(2)

    # --dry-run: build requests and print without sending.
    if args.dry_run:
        for scenario in scenarios:
            print(f"\n--- {scenario.scenario_id}: {scenario.title} ---")
            session_id: str | None = None
            for step in scenario.steps:
                request = build_request(step, session_id)
                print(f"  {request.method} {request.path}")
                if request.body:
                    print(f"  Body: {json.dumps(request.body, indent=4, ensure_ascii=False)}")
                session_id = "dry-run-session"
        sys.exit(0)

    # Determine timeout: CLI flag > env/.env > default 60.
    timeout = args.timeout if args.timeout is not None else _read_env_timeout()
    timeout = max(30.0, timeout)

    send = _make_http_send(args.base_url, timeout)

    # Preflight: check API reachability.
    try:
        health_req = Request(method="GET", path="/api/health", body=None)
        health_resp = send(health_req)
        if health_resp.status >= 500:
            print(
                f"API health check returned {health_resp.status}.",
                file=sys.stderr,
            )
            sys.exit(2)
    except ConnectionError as exc:
        print(f"API unreachable: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"Preflight check failed: {exc}", file=sys.stderr)
        sys.exit(2)

    # Run scenarios.
    results: list[ScenarioResult] = []
    total_passed = 0
    total_failed = 0
    total_steps = 0

    for scenario in scenarios:
        if args.verbose:
            print(f"\n{'=' * 60}")
            print(f"  {scenario.scenario_id}: {scenario.title}")
            print(f"{'=' * 60}")

        result = run_scenario(scenario, send)
        results.append(result)

        for sr in result.steps:
            total_steps += 1
            elapsed = f" ({sr.elapsed_ms:.0f}ms)" if sr.elapsed_ms is not None else ""
            if args.verbose:
                print(f"  [{sr.step.name}]")
                print(f"    Request:  {sr.request.method} {sr.request.path}")
                if sr.request.body:
                    body_preview = json.dumps(sr.request.body, ensure_ascii=False)
                    if len(body_preview) > 200:
                        body_preview = body_preview[:200] + "..."
                    print(f"    Body:     {body_preview}")
                if sr.response is not None:
                    resp_preview = json.dumps(sr.response.body, ensure_ascii=False)
                    if len(resp_preview) > 300:
                        resp_preview = resp_preview[:300] + "..."
                    print(f"    Response: status={sr.response.status}{elapsed}")
                    print(f"    Body:     {resp_preview}")
                else:
                    print(f"    Response: (none){elapsed}")
                if sr.failures:
                    for f in sr.failures:
                        print(f"    FAIL:     {f}")
                else:
                    print("    PASS")

        if result.passed:
            total_passed += 1
            status = "PASSED"
        else:
            total_failed += 1
            status = "FAILED"
            if not args.verbose:
                for sr in result.steps:
                    for f in sr.failures:
                        print(f"  FAIL [{result.scenario.scenario_id}] {sr.step.name}: {f}")

        if not args.verbose:
            print(f"  {status}  {result.scenario.scenario_id}  ({len(result.steps)} steps)")

    # Always write a full report to a file.
    report_path = Path(args.json_report) if args.json_report else _default_report_path()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_data = {
        "base_url": args.base_url,
        "timeout": timeout,
        "total_scenarios": len(results),
        "passed": total_passed,
        "failed": total_failed,
        "scenarios": [r.to_json() for r in results],
    }
    report_path.write_text(
        json.dumps(report_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nReport written to {report_path}")

    # Summary.
    print(f"\n{total_passed} passed, {total_failed} failed, {total_steps} steps total.")

    if total_failed > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
