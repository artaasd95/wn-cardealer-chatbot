# Edge Cases

This project treats edge cases as executable behavior, not just prose. The JSON
files under `tests/scenarios/edge/` are runnable scenario samples, and the
remaining provider, configuration, and database edge cases are covered by the
Python test suite.

See also:

- [Scenario harness reference](../tests/scenarios/README.md)
- [Architecture overview](architecture.md)

## How the Project Handles Edge Cases

- The LLM only interprets intent and extracts entities.
- SQL-backed repositories remain the source of truth for cars and dealers.
- The session store owns conversation state and partial scheduling context.
- Domain validation rejects invalid dates and illegal state transitions before
  persistence.
- Provider and infrastructure failures degrade to stable fallback behavior
  rather than producing uncaught exceptions for the user.

## Edge-Case Coverage Map

| Edge case | Handling | Sample |
| --- | --- | --- |
| No session id | Start a fresh session instead of failing | [edge_01_session_no_or_invalid_id](../tests/scenarios/edge/01_session_no_or_invalid_id.json) |
| Invalid session id | Replace it with a fresh live session id | [edge_01_session_no_or_invalid_id](../tests/scenarios/edge/01_session_no_or_invalid_id.json) |
| Expired or missing in-memory session | Treat it like a missing session and create a new one | [test_load_session_use_case.py](../tests/unit/use_cases/test_load_session_use_case.py) |
| Empty input | Reject at DTO validation with 422 | [edge_03_input_validation](../tests/scenarios/edge/03_input_validation.json) |
| Very long input | Accept at boundary length 2000, reject at 2001 | [edge_03_input_validation](../tests/scenarios/edge/03_input_validation.json) |
| User changes task mid-flow | Keep the state legal and answer in-band | [edge_04_change_task_mid_flow](../tests/scenarios/edge/04_change_task_mid_flow.json) |
| User restarts conversation | Delete the session and start fresh | [edge_02_restart_mid_flow](../tests/scenarios/edge/02_restart_mid_flow.json) |
| "yes" without a clear referent | Re-ask or clarify instead of guessing | [edge_05_ambiguous_reference](../tests/scenarios/edge/05_ambiguous_reference.json) |
| "that car" with multiple matches | Re-list candidates instead of silently picking one | [edge_05_ambiguous_reference](../tests/scenarios/edge/05_ambiguous_reference.json) |
| Unrelated question | Decline gracefully and steer back to supported tasks | [edge_06_unrelated_question](../tests/scenarios/edge/06_unrelated_question.json) |
| Car not found | Return a not-found branch, not an exception | [edge_07_car_not_found](../tests/scenarios/edge/07_car_not_found.json) |
| Multiple cars match | Return disambiguation candidates | [edge_08_multiple_matches](../tests/scenarios/edge/08_multiple_matches.json) |
| Positional disambiguation pick | Resolve "second option", "option 3", etc. against stored candidates | [edge_08_multiple_matches](../tests/scenarios/edge/08_multiple_matches.json) |
| Make-only query | Return either a safe disambiguation or a valid match | [edge_09_partial_criteria](../tests/scenarios/edge/09_partial_criteria.json) |
| Model-only query | Return either a safe disambiguation or a valid match | [edge_09_partial_criteria](../tests/scenarios/edge/09_partial_criteria.json) |
| Variant-only query | Return either a safe disambiguation or a valid match | [edge_09_partial_criteria](../tests/scenarios/edge/09_partial_criteria.json) |
| Misspelled make or model | Normalize when possible, otherwise fail safely | [edge_10_misspelled_make](../tests/scenarios/edge/10_misspelled_make.json) |
| Different capitalization | Normalize before lookup | [edge_11_capitalization_and_aliases](../tests/scenarios/edge/11_capitalization_and_aliases.json) |
| Alternative names and abbreviations | Expand aliases before authoritative search | [edge_11_capitalization_and_aliases](../tests/scenarios/edge/11_capitalization_and_aliases.json) |
| Missing variant | Show the row without inventing missing data | [edge_12_missing_variant](../tests/scenarios/edge/12_missing_variant.json) |
| Car exists but dealer does not | Keep the car selection and guard dealer-only tasks | [edge_13_car_without_dealer](../tests/scenarios/edge/13_car_without_dealer.json) |
| Invalid or incomplete car data | Return a safe clarification or fallback branch | [edge_14_incomplete_car_data](../tests/scenarios/edge/14_incomplete_car_data.json) |
| User changes selected car | Replace the selection and keep the state legal | [edge_15_change_selected_car](../tests/scenarios/edge/15_change_selected_car.json) |
| Dealer details before any selection | Ask the user to pick a car first | [edge_16_details_before_or_without_selection](../tests/scenarios/edge/16_details_before_or_without_selection.json) |
| No selected dealer | Guard the request and answer in-band | [edge_13_car_without_dealer](../tests/scenarios/edge/13_car_without_dealer.json) |
| Dealer does not exist | Return a safe explanatory response | [edge_18_another_dealer](../tests/scenarios/edge/18_another_dealer.json) |
| Dealer has incomplete details | Return partial details instead of crashing | [edge_17_incomplete_dealer_details](../tests/scenarios/edge/17_incomplete_dealer_details.json) |
| User asks for another dealer | Explain the limitation without fabricating one | [edge_18_another_dealer](../tests/scenarios/edge/18_another_dealer.json) |
| Missing date | Ask specifically for the date | [edge_19_schedule_missing_fields](../tests/scenarios/edge/19_schedule_missing_fields.json) |
| Missing time | Ask specifically for the time | [edge_19_schedule_missing_fields](../tests/scenarios/edge/19_schedule_missing_fields.json) |
| Ambiguous date | Ask a clarification question instead of guessing | [edge_20_schedule_ambiguous](../tests/scenarios/edge/20_schedule_ambiguous.json) |
| Ambiguous time | Ask a clarification question instead of guessing | [edge_20_schedule_ambiguous](../tests/scenarios/edge/20_schedule_ambiguous.json) |
| Ambiguous timezone | Ask which timezone the user intended | [edge_20_schedule_ambiguous](../tests/scenarios/edge/20_schedule_ambiguous.json) |
| Past date or time | Reject before persistence | [edge_21_schedule_rejected](../tests/scenarios/edge/21_schedule_rejected.json) |
| Invalid date text | Ask again instead of persisting garbage | [edge_21_schedule_rejected](../tests/scenarios/edge/21_schedule_rejected.json) |
| Invalid time text | Ask again instead of persisting garbage | [edge_21_schedule_rejected](../tests/scenarios/edge/21_schedule_rejected.json) |
| "Tomorrow afternoon" | Keep the partial context and ask for the missing hour | [edge_20_schedule_ambiguous](../tests/scenarios/edge/20_schedule_ambiguous.json) |
| "Friday at 3" | Ask whether the hour means morning or afternoon | [edge_20_schedule_ambiguous](../tests/scenarios/edge/20_schedule_ambiguous.json) |
| User changes requested time | Re-enter clarification flow rather than silently reusing stale state | [edge_22_schedule_changes_cancel](../tests/scenarios/edge/22_schedule_changes_cancel.json) |
| User cancels scheduling | Avoid confirming or persisting a misleading booking | [edge_22_schedule_changes_cancel](../tests/scenarios/edge/22_schedule_changes_cancel.json) |
| User asks to schedule another dealer | Keep behavior grounded in the current selected dealer context | [edge_22_schedule_changes_cancel](../tests/scenarios/edge/22_schedule_changes_cancel.json) |
| Prompt injection | Do not reveal prompts or change system behavior | [edge_23_llm_behavioral](../tests/scenarios/edge/23_llm_behavioral.json) |
| Hallucinated car | Never return a catalog result that SQL cannot confirm | [edge_23_llm_behavioral](../tests/scenarios/edge/23_llm_behavioral.json) |
| Hallucinated dealer | Never return a dealer that the repository cannot confirm | [edge_23_llm_behavioral](../tests/scenarios/edge/23_llm_behavioral.json) |
| Wrong intent classification | Route conservatively and degrade safely | [edge_23_llm_behavioral](../tests/scenarios/edge/23_llm_behavioral.json) |
| Unexpected response format | Treat it as ordinary text and keep the app stable | [edge_23_llm_behavioral](../tests/scenarios/edge/23_llm_behavioral.json) |
| LLM timeout | Return fallback behavior instead of a 500 | [edge_24_llm_degraded_contract](../tests/scenarios/edge/24_llm_degraded_contract.json) |
| LLM API failure | Return fallback behavior instead of a 500 | [edge_24_llm_degraded_contract](../tests/scenarios/edge/24_llm_degraded_contract.json) |
| Rate limit | Return fallback behavior after retry budget exhaustion | [edge_24_llm_degraded_contract](../tests/scenarios/edge/24_llm_degraded_contract.json) |
| Invalid structured output | Fall back deterministically | [test_openai_compatible_fallbacks.py](../tests/unit/llm_factory/test_openai_compatible_fallbacks.py) |
| Unknown `LLM_PROVIDER` | Fail fast at startup | [test_dependencies.py](../tests/integration/api/test_dependencies.py) |
| Missing `LLM_API_KEY` | Fail fast during settings validation | [test_settings.py](../tests/unit/test_settings.py) |
| Malformed `LLM_BASE_URL` | Fail fast during settings validation | [test_settings.py](../tests/unit/test_settings.py) |
| Unsupported or wrong endpoint credentials | Fall back without leaking secrets | [test_openai_compatible_fallbacks.py](../tests/unit/llm_factory/test_openai_compatible_fallbacks.py) |
| Settings changed mid-process | Keep using the startup-time singleton configuration | [test_dependencies.py](../tests/integration/api/test_dependencies.py) |
| Missing CSV files | Build schema and continue with empty tables | [test_repository_edge_cases.py](../tests/integration/repositories/test_repository_edge_cases.py) |
| Empty CSV files | Leave tables empty without crashing | [test_repository_edge_cases.py](../tests/integration/repositories/test_repository_edge_cases.py) |
| Malformed CSV files | Fail loudly instead of loading corrupt data | [test_repository_edge_cases.py](../tests/integration/repositories/test_repository_edge_cases.py) |
| Duplicate rows | Surface integrity or repository-level failure clearly | [test_repository_edge_cases.py](../tests/integration/repositories/test_repository_edge_cases.py) |
| Invalid dealer reference | Keep the session safe and guard follow-up tasks | [edge_13_car_without_dealer](../tests/scenarios/edge/13_car_without_dealer.json) |
| Invalid car fields | Normalize or degrade safely instead of crashing | [edge_12_missing_variant](../tests/scenarios/edge/12_missing_variant.json) |
| Query or transaction failure | Surface a controlled failure path | [test_repository_edge_cases.py](../tests/integration/repositories/test_repository_edge_cases.py) |

## Executable Edge-Case Scenario Files

These JSON files are executable samples. They are not just documentation; they
are consumed by the live scenario runner and the in-process pytest bridge.

| File | Purpose |
| --- | --- |
| [01_session_no_or_invalid_id.json](../tests/scenarios/edge/01_session_no_or_invalid_id.json) | Missing, invalid, or replaced session identifiers |
| [02_restart_mid_flow.json](../tests/scenarios/edge/02_restart_mid_flow.json) | Restarting the conversation mid-flow |
| [03_input_validation.json](../tests/scenarios/edge/03_input_validation.json) | Empty, whitespace-only, missing-field, and long-message boundaries |
| [04_change_task_mid_flow.json](../tests/scenarios/edge/04_change_task_mid_flow.json) | Switching tasks before finishing the current one |
| [05_ambiguous_reference.json](../tests/scenarios/edge/05_ambiguous_reference.json) | Vague replies such as `yes` or `that car` |
| [06_unrelated_question.json](../tests/scenarios/edge/06_unrelated_question.json) | Out-of-scope user questions |
| [07_car_not_found.json](../tests/scenarios/edge/07_car_not_found.json) | No matching car and recovery afterwards |
| [08_multiple_matches.json](../tests/scenarios/edge/08_multiple_matches.json) | Multiple catalog matches needing disambiguation |
| [09_partial_criteria.json](../tests/scenarios/edge/09_partial_criteria.json) | Make-only, model-only, and variant-only requests |
| [10_misspelled_make.json](../tests/scenarios/edge/10_misspelled_make.json) | Misspelled make or model text |
| [11_capitalization_and_aliases.json](../tests/scenarios/edge/11_capitalization_and_aliases.json) | Capitalization differences and alias handling |
| [12_missing_variant.json](../tests/scenarios/edge/12_missing_variant.json) | Seeded car row with missing variant details |
| [13_car_without_dealer.json](../tests/scenarios/edge/13_car_without_dealer.json) | Seeded car row whose dealer reference does not resolve |
| [14_incomplete_car_data.json](../tests/scenarios/edge/14_incomplete_car_data.json) | Vague user request with almost no extractable structure |
| [15_change_selected_car.json](../tests/scenarios/edge/15_change_selected_car.json) | Replacing the selected car during scheduling |
| [16_details_before_or_without_selection.json](../tests/scenarios/edge/16_details_before_or_without_selection.json) | Dealer-detail requests before a valid selection |
| [17_incomplete_dealer_details.json](../tests/scenarios/edge/17_incomplete_dealer_details.json) | Seeded dealer row with incomplete contact data |
| [18_another_dealer.json](../tests/scenarios/edge/18_another_dealer.json) | Requests for a different or non-existent dealer |
| [19_schedule_missing_fields.json](../tests/scenarios/edge/19_schedule_missing_fields.json) | Scheduling with missing date or time |
| [20_schedule_ambiguous.json](../tests/scenarios/edge/20_schedule_ambiguous.json) | Ambiguous date, time, timezone, and part-of-day phrasing |
| [21_schedule_rejected.json](../tests/scenarios/edge/21_schedule_rejected.json) | Past, unreadable, or invalid schedule inputs |
| [22_schedule_changes_cancel.json](../tests/scenarios/edge/22_schedule_changes_cancel.json) | Changing, cancelling, or re-routing scheduling |
| [23_llm_behavioral.json](../tests/scenarios/edge/23_llm_behavioral.json) | Prompt injection, hallucination pressure, and wrong-intent requests |
| [24_llm_degraded_contract.json](../tests/scenarios/edge/24_llm_degraded_contract.json) | Stable user contract during provider degradation |