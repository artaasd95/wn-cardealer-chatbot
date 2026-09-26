# Project Response

This document answers the project brief directly and maps each requirement to
the implementation in this repository.

Repository: <https://github.com/artaasd95/wn-cardealer-chatbot>

## 1. Objective

The project delivers an LLM-powered chatbot that helps a user:

1. identify a car they want to buy,
2. retrieve the matching dealer from generated CSV data,
3. choose either dealer details or call scheduling,
4. receive a final response grounded in authoritative catalog data.

The implementation deliberately keeps the LLM in an assistive role: it extracts
intent and entities, while repositories and workflow state determine what the
system is actually allowed to do.

## 2. Conversation Flow

The implemented flow follows the project brief:

1. The user asks for a car.
2. The chatbot looks up the car in generated CSV-backed data.
3. It returns the matching car and dealer when one row is confirmed.
4. It offers the next actions: dealer details or schedule a call.
5. Dealer details returns dealer contact information.
6. Scheduling asks for a date/time if missing, then confirms the chosen slot
   together with the dealer's name and phone number.

The flow is supported by a session-backed state machine so partial or ambiguous
conversations still behave predictably.

## 3. Technical Requirements

### Language

Python is used throughout the project.

### LLM

The project uses an LLM through the `openai` Python SDK, wrapped behind
`ports.llm.LLMPort` and implemented in
`infrastructure.llm.openai_compatible.OpenAICompatibleClient`.

Rationale for the SDK choice: the implementation uses the official OpenAI
Python SDK for simplicity, precise control over request/response handling, and
alignment with best-practice design. The SDK provides a stable, documented
interface with helpful timeout and retry hooks, telemetry/diagnostics support,
and straightforward compatibility with OpenAI-wire-compatible endpoints. The
client is wrapped behind `LLMPort` so provider-specific details remain isolated
from core business logic and are easy to replace or mock for testing.

The provider is configurable. Any OpenAI-compatible endpoint can be used,
including hosted providers or local servers.

### Interface

The repository includes more than the minimum required interface surface:

- CLI chatbot: `cardealer`
- FastAPI HTTP API: `presentation.api.main:app`
- Streamlit web UI: `src/presentation/streamlit/app.py`

## 4. Data

The repository creates its own random but deterministic CSV fixtures through
`scripts/generate_data.py`.

### Data files

- `data/cars.csv`
- `data/dealers.csv`
- `data/aliases.csv`

### Current generated fixture sizes

- 156 car rows
- 14 dealer rows
- 33 alias rows

### Data design choices

- Cars reference dealers by `dealer_id`.
- Aliases are stored separately so user phrasing can be normalized before
  catalog lookup.
- The dataset intentionally includes both normal rows and seeded adversarial
  rows so edge-case behavior can be tested repeatedly.

## 5. Edge Cases

Edge cases were treated as a first-class design concern rather than a final
patch layer.

- Conversation and session edge cases are covered through scenario JSON files.
- Configuration and infrastructure edge cases are covered through unit and
  integration tests.
- The system degrades in-band with a useful reply whenever possible instead of
  leaking exceptions to users.

Detailed coverage is documented in [edge-cases.md](edge-cases.md).

## 6. Engineering Best Practices

### Project structure and packaging

- `src/` layout
- `pyproject.toml`
- installable distribution name: `wn-cardealer-chatbot`
- console script: `cardealer`

### Dependencies

- runtime and dev dependencies are declared in `pyproject.toml`
- the exact resolved versions are pinned in `requirements.txt`
  (`pip freeze` of the project virtual environment), so the environment is
  reproducible in a virtual environment
- no extra framework dependency was added for orchestration

### Code quality

- clear separation between presentation, application, domain, ports, and infrastructure
- type hints across the codebase
- modular use-case driven design
- linting and type-checking configuration included

### Configuration and secrets

- `.env.example` provided
- settings validated centrally in `config.settings`
- secrets are environment-driven and git-ignored

### Testing

- unit tests for core logic
- integration tests for repositories and API
- JSON scenario harnesses for normal and edge-case conversations

### Error handling and logging

- graceful domain-level handling for common user and data problems
- deterministic fallback behavior for LLM failures
- centralized logging configuration in `config.logging`

### Version control

- `.gitignore` is present and protects secrets, local databases, and caches

## 7. Example Conversation

The exact wording in this project differs from the sample in the brief, but the
implemented behavior is equivalent.

Example happy path:

```text
User: I'm looking for a BMW 3 Series 320i 2021.
Bot: Found BMW 3 Series 320i (2021) ... Would you like dealer details or to schedule a call?
User: Schedule a call.
Bot: What date and time work for you?
User: 2030-05-15 at 3pm UTC.
Bot: Your call is booked for Wednesday, May 15, 2030 at 15:00 UTC (UTC local
     time) with Prestige Cars (+91-80-2552-1003). The dealer will call you then.
```

Like the brief's sample dialog, the confirmation carries the dealer's name,
phone number and the chosen slot.

## 8. Deliverables

The repository contains the requested deliverables:

- Python source code
- generated CSV data
- `.env.example`
- tests
- root README
- architecture and edge-case documentation

Repository link:

- <https://github.com/artaasd95/wn-cardealer-chatbot>


## Bonus Items Implemented

Beyond the minimum brief, the repository also includes:

- FastAPI API with OpenAPI docs
- Streamlit chat UI
- installable CLI chatbot
- deterministic scenario runner for edge-case conversations
- centralized logging configuration
- architecture documentation and explicit requirement mapping
