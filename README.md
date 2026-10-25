# veyra.

**Intelligence Behind Every Decision.**

VEYRA is a local-first product intelligence workspace that turns plain-language questions into explainable, validated queries over a SQLite product database. Phase 1 provides the complete question-to-results foundation: seeded product data, schema discovery, structured planning, optional local Ollama SQL generation, layered query safety, real query results, and a polished React interface.

## What works in Phase 1

- Reproducible synthetic users, sessions, events, orders, and experiment assignments
- SQLite table, column, key, and relationship discovery
- Pydantic-validated query plans and API responses
- Deterministic offline questions plus schema-aware Ollama generation for broader questions
- SQLGlot validation, read-only URI connections, SQLite authorizer, timeout, and row limit
- Results table, automatic bar chart, SQL inspection/copy, and honest clarification states
- Backend integration and SQL safety tests

Product metric semantics, experimentation analysis, investigations, ML, and benchmarking are deliberately deferred to their specified later phases.

## Architecture

```text
React/Vite ──POST /api/query──> FastAPI
                                  ├─ intent + structured plan
                                  ├─ SQLite schema catalog
                                  ├─ deterministic SQL OR Ollama
                                  ├─ SQLGlot validation
                                  └─ read-only SQLite execution ──> evidence + metadata
```

See [architecture](docs/architecture.md) and [database schema](docs/database-schema.md).

## Windows PowerShell setup

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\backend\requirements.txt
python .\scripts\generate_dataset.py
Set-Location .\backend
uvicorn app.main:app --reload
```

In a second PowerShell window:

```powershell
Set-Location .\frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The deterministic examples work without Ollama.

### Optional local model

Install Ollama separately, then run:

```powershell
ollama pull qwen2.5-coder:1.5b
ollama serve
```

VEYRA detects the model automatically at `http://127.0.0.1:11434`. Configuration values are listed in [.env.example](.env.example).

## Tests and checks

```powershell
Set-Location .\backend
pytest

Set-Location ..\frontend
npm run build
npm run test
```

API documentation is available at `http://127.0.0.1:8000/docs` while the backend is running.

## Known limitations

- Deterministic offline language coverage is intentionally small; Ollama expands coverage.
- Phase 1 validates tables but does not yet perform full semantic column lineage for every SQL expression.
- SQLite is the only database adapter implemented.
- Timezone normalization, metric definitions, cohort math, and experiments arrive in later phases.
- Ollama output quality depends on the locally installed model and machine.

