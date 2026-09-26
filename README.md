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
| `LLM_TIMEOUT_SECONDS` | Per-request timeout |
| `LLM_MAX_RETRIES` | Retry budget before fallback behavior |
| `APP_ENV` | Environment label |
| `APP_HOST`, `APP_PORT` | API host and port |
| `APP_LOG_LEVEL` | Project-wide log level |
| `APP_LOG_FILE` | Optional rotating log file path |
| `DATABASE_URL` | SQLAlchemy connection string |
| `SESSION_TTL_SECONDS` | In-memory conversation TTL |

The application validates configuration centrally at startup and fails fast on
bad provider settings.

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
cases.

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

### Run only edge-case scenarios

```bash
python scripts/run_scenarios.py --suite edge
python scripts/run_scenarios.py --suite edge --tag schedule_call --verbose
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

## How This Answers the Project Brief

The direct, numbered response to the attached project brief is documented in
[docs/project-response.md](docs/project-response.md).
