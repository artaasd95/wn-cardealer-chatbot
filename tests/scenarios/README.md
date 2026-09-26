# Scenario payloads — usual and edge-case conversations

This directory holds the chat-API scenario payloads in two suites:

```
tests/scenarios/
├── normal/   # the usual, happy-path conversations (plan.md §2 main flows)
├── edge/     # the edge cases from plan.md §3, one file per case
└── README.md # this file
```

Each `*.json` file is a small conversation: ordered `steps`, where every step
is **a ready-to-send HTTP request** plus the **acceptance rules** the response
must satisfy (including regular expressions over the free-text reply).

Two harnesses execute exactly the same files:

| Harness | Command | LLM | Use |
|---|---|---|---|
| Live runner | `python scripts/run_scenarios.py` | real provider from `.env` | against a running server |
| pytest bridge | `pytest tests/integration/api/test_scenarios.py` | scripted fake | deterministic CI run |

---

## Scenario schema

```jsonc
{
  "id": "edge_32_past_date",            // unique id (also the pytest test name)
  "title": "Past date is rejected",
  "suite": "edge",                       // "normal" or "edge" (must match the directory)
  "description": "…",                    // what the scenario proves
  "plan_refs": ["plan.md §3 Schedule: Past date/time"],   // traceability
  "tags": ["schedule_call"],             // filter with --tag
  "notes": "optional extra context",

  "steps": [
    {
      "name": "ask for a date that already passed",

      // --- the request -------------------------------------------------
      "method": "POST",                  // default POST
      "path": "/api/chat",               // default /api/chat
      "request": {                       // JSON body (POST); omitted for GET/DELETE
        "session_id": "$session",        // placeholder, see below
        "message": "2020-01-01 at 10am"
      },

      // --- scripted LLM (ignored by the live runner) --------------------
      "llm": {
        "intent": "SCHEDULE_CALL",                        // TaskDecision.task_type
        "car": {"make": "BMW", "model": "3 Series"},       // CarExtraction fields
        "schedule": {"date_raw": "2020-01-01", "time_raw": "10am"}, // ScheduleExtraction
        "reply": ""                                        // ResponseWording; "" = deterministic fallback
      },

      // --- acceptance ---------------------------------------------------
      "expect": {
        "status": 200,
        "body": {
          "workflow_state": {"equals": "AWAITING_DATETIME"},
          "reply": {
            "all_of":   [{"regex": "already passed"}],
            "must_not": [{"regex": "booked for"}]
          }
        }
      }
    }
  ]
}
```

### Placeholders

| Placeholder | Replaced with |
|---|---|
| `$session` | the `session_id` captured from the most recent response of this scenario (also usable inside `expect`, e.g. `{"equals": "$session"}` asserts continuity) |
| `$long_message:N` | a message of exactly `N` characters (`"aaa…"`), for the DTO length boundaries |

### Acceptance matchers

A matcher is either a **literal** (compared with `==`) or an **object** whose
keys are combined with AND. Regexes are Python patterns applied with
`re.search`, **case-insensitive by default** (use `(?-i:…)` for a strict
match). Everything that is not a string is compared structurally.

| Key | Meaning |
|---|---|
| `equals` | exact equality |
| `in` | value is one of the list |
| `regex` | regex search (case-insensitive) |
| `any_of` | at least one sub-matcher passes |
| `all_of` | every sub-matcher passes |
| `must_not` | no sub-matcher passes |
| `min_length` / `max_length` | string length bounds |
| `min_items` / `max_items` | list length bounds |
| `contains_all` | each pattern matches at least one list item |
| `contains_any` | some pattern matches some list item |
| `exists` | `true`/`false`: whether the field is present (non-null) |

`expect.status` uses the same matcher language (`200` or `{"in": [422]}`).

### Strict vs tolerant

* `normal/` asserts **exact contracts** where the reply is deterministic
  (found/not-found/disambiguation wording, state, suggested actions).
* `edge/` asserts the **graceful-degradation contract**: status 200 (never
  500), a legal state, a clarification question, and `must_not` rules against
  hallucinated cars/dealers or leaked prompt text. Where the live provider's
  wording may vary, `any_of` accepts both the LLM wording and the
  deterministic fallback.

---

## Coverage map (plan.md §3 edge cases)

| plan.md §3 case | Where it is covered |
|---|---|
| **Session / conversation** | |
| No session ID | `edge/01_session_no_or_invalid_id.json` |
| Invalid session ID | `edge/01_session_no_or_invalid_id.json` |
| Expired/missing in-memory session | `tests/unit/use_cases/test_load_session_use_case.py` (TTL cannot expire over HTTP in one run) |
| Empty input | `edge/03_input_validation.json` |
| Very long input | `edge/03_input_validation.json` |
| User changes task mid-flow | `edge/04_change_task_mid_flow.json` |
| User restarts conversation | `edge/02_restart_mid_flow.json`, `normal/08_restart_conversation.json` |
| "yes" without clear referent | `edge/05_ambiguous_reference.json` |
| "that car" with multiple matches | `edge/05_ambiguous_reference.json` |
| Unrelated question | `edge/06_unrelated_question.json` |
| **Item lookup** | |
| Car not found | `edge/07_car_not_found.json` |
| Multiple cars match | `edge/08_multiple_matches.json`, `normal/05_disambiguation_then_pick.json` |
| Make only / model only / variant only | `edge/09_partial_criteria.json` |
| Misspelled make/model | `edge/10_misspelled_make.json` |
| Different capitalization | `edge/11_capitalization_and_aliases.json` |
| Alternative names/abbreviations | `edge/11_capitalization_and_aliases.json`, `normal/06_alias_and_normalization.json` |
| Missing variant | `edge/12_missing_variant.json` (seeded C-9002) |
| Car exists but dealer doesn't | `edge/13_car_without_dealer.json` (seeded C-9004 → D-999) |
| Invalid/incomplete car data | `edge/12_missing_variant.json`, `edge/14_incomplete_car_data.json` |
| User changes selected car | `edge/15_change_selected_car.json`, `normal/10_find_another_car.json` |
| **Dealer details** | |
| No selected car / no selected dealer | `edge/16_details_before_or_without_selection.json`, `edge/13_car_without_dealer.json` |
| Dealer doesn't exist | `edge/13_car_without_dealer.json`, `edge/18_another_dealer.json` |
| Dealer has incomplete details | `edge/17_incomplete_dealer_details.json` (seeded D-012) |
| User asks for another dealer | `edge/18_another_dealer.json` |
| Details before car lookup | `edge/16_details_before_or_without_selection.json` |
| **Schedule** | |
| No selected dealer | `edge/13_car_without_dealer.json` |
| Missing date / missing time | `edge/19_schedule_missing_fields.json` |
| Ambiguous date / time / timezone | `edge/20_schedule_ambiguous.json` |
| "Tomorrow afternoon" / "Friday at 3" | `edge/20_schedule_ambiguous.json` |
| Past date/time | `edge/21_schedule_rejected.json` |
| Invalid date / invalid time | `edge/21_schedule_rejected.json` |
| User changes requested time | `edge/22_schedule_changes_cancel.json` |
| User cancels scheduling | `edge/22_schedule_changes_cancel.json` |
| User asks to schedule another dealer | `edge/22_schedule_changes_cancel.json` |
| **LLM behavioural** | |
| Prompt injection | `edge/23_llm_behavioral.json` |
| Hallucinated car / dealer | `edge/23_llm_behavioral.json` |
| Wrong intent classification | `edge/23_llm_behavioral.json` |
| Unexpected response format | `edge/23_llm_behavioral.json` (raw-JSON message) |
| Timeout / API failure / rate limit / empty / truncated / retry exhausted | `edge/24_llm_degraded_contract.json` (HTTP contract) + `tests/unit/llm_factory/test_openai_compatible_fallbacks.py` (adapter behaviour) |
| **Configuration** | |
| Unknown provider / missing key / bad base URL | `tests/unit/test_settings.py`, `tests/integration/api/test_dependencies.py` |
| Client built once, `.env` changes mid-process | `tests/integration/api/test_dependencies.py` |
| **Database / infrastructure** | |
| Missing / empty / malformed CSV, duplicates | `tests/integration/repositories/test_repository_edge_cases.py` |
| Invalid dealer reference, invalid car fields | `tests/integration/repositories/test_repository_edge_cases.py`, `edge/13_car_without_dealer.json`, `edge/12_missing_variant.json` |
| Query / transaction failure, unreachable DB | `tests/integration/repositories/test_repository_edge_cases.py` |

## Running

```bash
# 1. start the API (terminal 1)
uvicorn src.presentation.api.main:app --port 8000

# 2. run the payloads against it (terminal 2)
python scripts/run_scenarios.py --list                 # what is there
python scripts/run_scenarios.py --dry-run              # resolve requests, send nothing
python scripts/run_scenarios.py                        # both suites
python scripts/run_scenarios.py --suite edge --tag schedule_call --verbose
python scripts/run_scenarios.py --json-report report.json

# or run the same files in-process with the scripted LLM
pytest tests/integration/api/test_scenarios.py -q
```
