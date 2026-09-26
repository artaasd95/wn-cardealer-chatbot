# wn-cardealer-chatbot

A car-dealer chatbot: identify the car, retrieve the matching car/dealer data,
then either show the dealer's details or schedule a call.

Built as a clean-architecture Python project — one layer per concern, contracts
(DTO/models) at the boundaries, ports for every external effect, and adapters
under `infrastructure/`. **No LLM framework is used**: no LangGraph, no
LangChain. The workflow state machines are plain Python classes in
`application/tasks/*/workflow.py`, and every LLM call goes through one port
(`ports/llm.py`) whose provider is selected purely by `.env`.

---

## Requirements

- Python **3.12+** (the pinned environment is `.venv`, Python 3.13.9)
- No external services: the database defaults to SQLite and the session store
  is in-memory

## Setup

```bash
# from the repository root
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e ".[dev]"            # runtime + dev dependencies (pytest, ruff, mypy)

cp .env.example .env               # then edit the values (see below)
```

## Configuration (`.env`)

Every key has a working default in `.env.example`, so the file is
copy-and-runnable. `config/settings.py` validates them **once at startup** and
refuses to boot on a bad value (unknown provider, missing API key, malformed
base URL).

| Key | Meaning |
| --- | --- |
| `LLM_PROVIDER` | The only switch needed — currently `openai_compatible` |
| `LLM_BASE_URL` | Any OpenAI-compatible `/v1` endpoint (OpenAI, Azure, Groq, Together, Ollama, vLLM, LM Studio) |
| `LLM_API_KEY` | API key for that endpoint (placeholder in `.env.example`) |
| `LLM_MODEL` | Model name served by the endpoint |
| `LLM_TEMPERATURE` | `0.0` — extraction must be deterministic |
| `LLM_TIMEOUT_SECONDS` | Per-request timeout |
| `LLM_MAX_RETRIES` | Retry budget before the client degrades to its fallback |
| `APP_ENV`, `APP_HOST`, `APP_PORT` | Runtime environment |
| `DATABASE_URL` | Defaults to `sqlite:///./cardealer.db` |
| `SESSION_TTL_SECONDS` | Conversational session lifetime |

Swapping provider or endpoint is **configuration only** — no code change.

## Data

The catalog is generated deterministically from `scripts/generate_data.py`:

```bash
python scripts/generate_data.py            # write data/cars.csv, dealers.csv, aliases.csv
python scripts/generate_data.py --check    # validate the CSVs without rewriting them
```

The CSVs are loaded into the database automatically on first startup (only when
the tables are empty). `data/aliases.csv` is loaded by the car repository so
user-typed aliases (`B.M.W.`, `Merc`, `C Class`) resolve to canonical catalog
values during search.

## Running the API

```bash
uvicorn presentation.api.main:app --reload
```

- `POST /api/chat` — one chat turn (`{"session_id": ..., "message": ...}`)
- `GET /api/health` — liveness + the resolved provider name (never the key)
- `DELETE /api/sessions/{session_id}` — restart the conversation
- Interactive docs: <http://localhost:8000/docs>

Example:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I am looking for a BMW"}'
```

## Running the chat UI

```bash
streamlit run src/presentation/streamlit/app.py
```

The UI talks to the API only (`API_BASE_URL` from the environment, then
`.streamlit/secrets.toml`, then `http://localhost:8000`). It renders the
`suggested_actions` returned in the response DTO as clickable next steps.

## Tests, lint, types

```bash
pytest                      # full suite
pytest -m unit              # fast, isolated tests
pytest -m integration       # database + HTTP layer
pytest --cov=src --cov-report=term-missing

ruff check .                # lint (import ordering, architecture rules)
ruff format --check .       # formatting
mypy src                    # strict type checking
```

## Architecture

```
src/
├── DTO/            boundary contracts (what FastAPI accepts/returns)
├── models/         internal contracts (LLM inputs, repository outputs)
├── domain/         entities, enums, exceptions, parsing rules — no I/O
├── application/    use cases, chat facade, task router, workflow state machines
├── ports/          protocols: LLMPort, SessionStore, repositories
├── infrastructure/ adapters: SQLAlchemy repos, in-memory session, LLM client + prompts
├── presentation/   FastAPI routes/dependencies and the Streamlit UI
└── config/         .env → typed settings, validated once at startup
```

Flow of one turn: `DTO/inputs/chat.py` → load session → intent extraction
(`LLMPort`) → `TaskRouter` (state-guarded) → task use case → repository →
workflow state advance (validated against `LEGAL_TRANSITIONS`) → save session →
`DTO/outputs/chat.py`.

The LLM never decides the workflow and never invents catalog data: it extracts
entities and words replies, while SQL provides the authoritative car/dealer
data and the session store owns the state machine.
