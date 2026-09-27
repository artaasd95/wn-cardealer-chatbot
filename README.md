# wn-cardealer-chatbot

`wn-cardealer-chatbot` is an installable Python package that implements the AI
Engineer project brief: an LLM-powered car dealer assistant that helps a
user find a car, retrieve the selling dealer, and either show dealer details or
schedule a call.

Repository: <https://github.com/artaasd95/wn-cardealer-chatbot>

The project goes beyond the minimum CLI requirement and provides:

- an installable CLI chatbot (`cardealer`)
- a FastAPI HTTP API
- a Streamlit web UI
- deterministic scenario suites for normal and edge-case conversations

## What the Project Does

The assistant follows the project brief's core conversation flow:

1. greet the user and ask or infer which car they want,
2. look it up in the seeded catalog database,
3. return the matching car and dealer,
4. offer dealer details or call scheduling,
5. either show the dealer's information or confirm a requested time slot.

Along the way the assistant keeps session memory: greetings are handled
directly, contextual questions ("what cars did I see?", "which is cheaper?")
are answered from the cars shown so far, and follow-up references to earlier
options resolve against the same history.

The LLM is used for intent extraction, entity extraction, and response wording.
It does not control the workflow and it does not invent authoritative catalog
results.

## Documentation

- [Architecture details](docs/architecture.md)
- [Edge-case handling and executable scenario links](docs/edge-cases.md)
- [Project response](docs/project-response.md)
- [Scenario harness reference](tests/scenarios/README.md)

## Package and Installation

### Requirements

- Python 3.12+
- a configured OpenAI-compatible endpoint or local model server

### Install

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Alternatively, install the exact pinned dependency set first (captured from
the project virtual environment with `pip freeze`):

```bash
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]" --no-deps
```

The distribution name is `wn-cardealer-chatbot`.

After installation, the console entrypoint is available as:

```bash
cardealer
```

## Configuration

Copy `.env.example` to `.env` and set the model connection details.

```bash
copy .env.example .env
# macOS / Linux: cp .env.example .env
```

### Main settings

| Key | Purpose |
| --- | --- |
| `LLM_PROVIDER` | Provider key, currently `openai_compatible` |
| `LLM_BASE_URL` | OpenAI-compatible `/v1` endpoint |
| `LLM_API_KEY` | Provider or local-server token |
| `LLM_MODEL` | Model name served by the endpoint |
| `LLM_TEMPERATURE` | Kept at `0.0` for deterministic extraction |
| `LLM_TIMEOUT_SECONDS` | Per-request LLM timeout (default 30) |
| `LLM_MAX_RETRIES` | Retry budget before fallback behavior |
| `APP_REQUEST_TIMEOUT_SECONDS` | UI/API request timeout, minimum 30s (default 60) |
| `APP_ENV` | Environment label |
| `APP_HOST`, `APP_PORT` | API host and port |
| `APP_LOG_LEVEL` | Project-wide log level |
| `APP_LOG_FILE` | Optional rotating log file path |
| `DATABASE_URL` | SQLAlchemy connection string |
| `SESSION_TTL_SECONDS` | In-memory conversation TTL |

The application validates configuration centrally at startup and fails fast on
bad provider settings.

### Timeouts and request delays

Two timeout settings control how long the system waits before giving up:

| Setting | Where it applies | Default | Minimum |
| --- | --- | --- | --- |
| `LLM_TIMEOUT_SECONDS` | Each individual LLM API call (intent, extraction, wording) | 30s | none |
| `APP_REQUEST_TIMEOUT_SECONDS` | Streamlit → FastAPI HTTP request; scenario runner | 60s | 30s |

A single chat turn may call the LLM up to three times (intent classification,
entity extraction, response wording).  `APP_REQUEST_TIMEOUT_SECONDS` must be
larger than `LLM_TIMEOUT_SECONDS` so the UI does not disconnect while the
backend is still processing.  The minimum of 30s is enforced at startup — the
application refuses to launch with a lower value.

Both settings are read from `.env` (or environment variables) and documented in
`.env.example`.

## Data Design

The repository generates its own deterministic test data.

### Data files

- `data/cars.csv`
- `data/dealers.csv`
- `data/aliases.csv`

### Current generated fixture sizes

- 156 cars
- 14 dealers
- 33 aliases

### Design choices

- cars link to dealers via `dealer_id`
- aliases are stored separately to support normalization before lookup
- the generator includes normal rows and deliberately adversarial rows
- the output is deterministic, so tests and scenario examples are repeatable

### Generate or validate the fixtures

```bash
python scripts/generate_data.py
python scripts/generate_data.py --check
```

The database loader imports these CSV files automatically when the schema is
initialized and the tables are empty. After that first seed, all runtime
queries go through the database — the CSVs are never read per request.

## Running the Project

### 1. CLI chatbot

The CLI is the simplest way to use the assistant locally.

```bash
cardealer
```

Optional arguments:

```bash
cardealer --user-id demo-user
cardealer --session-id existing-session-id
```

CLI commands:

- `/help` prints quick usage
- `/reset` clears the current session
- `/quit` exits the program

### 2. FastAPI API

Start the backend first. When working from the repository (no install), the recommended command is:

```powershell
# Activate the venv (Windows PowerShell)
.venv\Scripts\Activate

# Run the API from the project sources (no install required)
python -m uvicorn src.presentation.api.main:app --reload --host 127.0.0.1 --port 8001
```

If you installed the package (`pip install -e ".[dev]"`) you can run the installed module path instead:

```powershell
uvicorn presentation.api.main:app --reload --host 127.0.0.1 --port 8001
```

Main endpoints:

- `POST /api/chat`
- `GET /api/health`
- `DELETE /api/sessions/{session_id}`

Interactive API docs:

- <http://127.0.0.1:8001/docs>

Example request (adjust host/port to match your `.env`):

```powershell
curl -X POST http://127.0.0.1:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": null, "message": "I want a BMW 3 Series 320i 2021"}'
```

### 3. Streamlit UI

Start the API first (see above), then run the Streamlit UI. From the repo root:

```powershell
streamlit run src/presentation/streamlit/app.py
```

How the Streamlit app finds the API:

1. `API_BASE_URL` environment variable (highest precedence)
2. Streamlit `secrets.toml` (`st.secrets`)
3. `APP_HOST` and `APP_PORT` from your `.env` (fallback)

If the default port `8000` is already in use on your machine (for example by Docker Desktop), either:

- set `API_BASE_URL` before launching Streamlit:

```powershell
$env:API_BASE_URL='http://127.0.0.1:8001'; streamlit run src/presentation/streamlit/app.py
```

- or copy and edit the `.env` file to change `APP_PORT` (for example to `8001`):

```powershell
copy .env.example .env
# then edit .env and set APP_PORT=8001
```

Logs

The API logs to stdout and — if `APP_LOG_FILE` is set in `.env` — to a rotating file. To follow the file on Windows PowerShell:

```powershell
Get-Content .\logs\api.log -Wait -Tail 20
```

## Testing and Quality Checks

Use the project interpreter for consistency.

```bash
python -m pytest
python -m pytest -m unit
python -m pytest -m integration
python -m pytest --cov=src --cov-report=term-missing

ruff check .
ruff format --check .
mypy src
```

## Scenario Testing

The repository includes executable scenario payloads for both normal and edge
cases.  Multi-stage scenarios cover the full conversation flows:

- **Standard flow** (`normal_flow_standard`): greeting → car search → dealer details → schedule
- **Complex flow** (`normal_flow_complex`): greeting → search → conversation → search → conversation → selection (car from 4 messages ago) → dealer details → schedule

### List the available scenarios

```bash
python scripts/run_scenarios.py --list
```

### Dry-run the request payloads without sending them

```bash
python scripts/run_scenarios.py --dry-run
```

### Run all scenarios against a live API

```bash
python scripts/run_scenarios.py
```

Full request/response logs are always written to `logs/scenario_runs/<timestamp>.json`.
Use `--json-report path.json` to choose a different path.

### Run only edge-case scenarios

```bash
python scripts/run_scenarios.py --suite edge
python scripts/run_scenarios.py --suite edge --tag schedule_call --verbose
```

### Configure the scenario runner timeout

The runner reads `APP_REQUEST_TIMEOUT_SECONDS` from `.env` (default 60, minimum
30).  Override with `--timeout`:

```bash
python scripts/run_scenarios.py --timeout 90
```

### Run the same scenario files through pytest with a scripted fake LLM

```bash
python -m pytest tests/integration/api/test_scenarios.py -q
```

## Edge Cases

Edge cases are handled explicitly across the application, not left to the LLM.

- not found, multiple-match, partial-input, and alias cases are routed through
  deterministic repository logic
- dealer and scheduling guards stop illegal follow-up actions cleanly
- ambiguous or invalid schedule inputs are clarified before persistence
- provider, configuration, and data-layer failures degrade safely or fail fast

The detailed coverage map, with direct links to every edge-case scenario JSON,
is in [docs/edge-cases.md](docs/edge-cases.md).

## Architecture Summary

The codebase uses a clean architecture with explicit boundaries:

```text
src/
├── DTO/            transport contracts
├── models/         internal data contracts
├── domain/         business rules and validation
├── application/    use cases, workflows, router, session logic
├── ports/          abstract interfaces
├── infrastructure/ concrete adapters and persistence
├── presentation/   CLI, API, Streamlit
└── config/         settings and logging
```

One turn follows this pattern:

1. receive `ChatRequest`
2. load or create the session
3. classify task intent through `LLMPort`
4. run the matching use case
5. confirm results through repositories
6. advance the workflow state legally
7. save the session
8. return `ChatResponse`

See [docs/architecture.md](docs/architecture.md) for the full architecture.

## Logging and Error Handling

Logging is configured centrally in `config.logging` and shared across the CLI,
API, Streamlit, repositories, and LLM adapter.

- `APP_LOG_LEVEL` controls verbosity
- `APP_LOG_FILE` optionally writes to a rotating file
- LLM failures degrade to deterministic fallbacks
- repository and session failures are logged with stable user-facing responses

## Assumptions and Design Decisions

Assumptions made for the assignment:

- **No real booking.** Scheduling a call writes a local record (SQLite table
  `schedule`) and confirms it; nothing is sent to an external booking service,
  as the brief states none is needed.
- **Catalog data is authoritative.** The chatbot never invents cars, dealers,
  prices or phone numbers. Anything the LLM says about catalog facts is
  grounded in repository results; unknown vehicles are refused rather than
  hallucinated.
- **Confirmation content.** Every booking confirmation carries the dealer's
  name, phone number and the chosen slot, matching the brief's example
  conversation. If the dealer row is missing or the lookup fails, the
  confirmation degrades to the slot alone instead of failing the booking.
- **Times are UTC-first.** A requested slot is stored in UTC with the user's
  stated zone kept alongside it. Ambiguous times ("Friday at 3") are clarified,
  never guessed; past times are refused.
- **Session memory is conversational only.** Seen cars, the selected car/dealer
  and workflow state live in an in-memory store with a TTL. This is deliberately
  not persistent user accounts — the brief scopes the assignment to one
  conversation.
- **Deterministic fixtures.** The CSV data is randomly generated but seeded, so
  every test and example in this README is reproducible.

Design decisions worth calling out:

- **The LLM interprets, the workflow decides.** Intent/entity extraction and
  response wording go through `LLMPort`; what the system may do next is
  enforced by a small state machine, so LLM failures cannot corrupt state.
- **Clean architecture boundaries.** `domain` has no framework imports,
  `application` depends only on `ports`, and `infrastructure` adapts the
  outside world (SQLite, OpenAI-compatible endpoints). Import rules are
  enforced by a test (`tests/unit/test_import_boundaries.py`).
- **Provider-agnostic LLM adapter.** Any OpenAI-wire-compatible endpoint works
  (hosted or local), configured entirely through `.env`.
- **Both wording paths.** Replies are LLM-worded where possible and fall back
  to deterministic templates on provider failure, so the assistant keeps
  working during an outage.

## How This Answers the Project Brief

The direct, numbered response to the attached project brief is documented in
[docs/project-response.md](docs/project-response.md).
