# veyra.

**Local product analytics, experimentation, and investigations.**

VEYRA is a project you run on your own computer. It includes a reproducible demo database, a React interface, and a FastAPI backend. No paid API key or cloud account is required. Ollama is optional; supported queries and analytical modules work without it.

**Release scope: single-person local preview.** Start with the [first-session guide](docs/local-preview-guide.md) for importing data, interpreting results and understanding privacy boundaries. This is not approved for public multi-user hosting, and SQL safety checks do not guarantee a correct business interpretation.

## Prerequisites

- Python **3.12** (the pinned backend environment is tested with this version).
- Node.js **24 LTS**, including npm. Node 22 or newer is accepted by setup; 24 is the tested version.
- Internet access for the first dependency installation.
- Windows, macOS, or Linux. Automated scripts are verified locally on Windows; Linux checks are defined in CI. macOS has not been independently verified.

Install Python and Node from their official distributions, then reopen your terminal. On Windows, check `py -3.12 --version`, `node --version`, and `npm --version`. Do not run the project from your home directory: open a terminal in this repository's folder.

## Quick start — Windows

From the repository root:

```powershell
py -3.12 scripts/setup.py
.\.venv\Scripts\python.exe scripts/run.py
```

Open [http://127.0.0.1:5173/](http://127.0.0.1:5173/). Keep the terminal open. **Ctrl+C stops both servers.** No virtual-environment activation or PowerShell execution-policy change is needed.

Setup creates `.venv`, installs the pinned Python dependencies, installs frontend dependencies with the pinned pnpm version through npm, and generates the demo database only if it is missing. Rerunning setup preserves existing databases and configuration.

## Quick start — macOS / Linux

```bash
python3.12 scripts/setup.py
.venv/bin/python scripts/run.py
```

The same local URL and Ctrl+C behavior apply. Native dependencies may need platform-specific wheels or build tools; the Windows dependency snapshot has not yet been certified on every operating system.

## Check your installation

```powershell
py -3.12 scripts/setup.py --check
```

This checks installed runtimes, dependencies, frontend files, and the demo database without reinstalling anything.

The API is available at `http://127.0.0.1:8000`, interactive API docs at `/docs`, liveness at `/livez`, and database readiness at `/readyz`.

## Five-minute demo

1. **Ask Veyra:** “Show users by country” or “Show all instances where users opened the app in March 2026.” Inspect the SQL and download CSV results.
2. **Product Analytics:** view activity, activation, retention, churn, and ordered conversion funnels.
3. **Experimentation Lab:** compare control and treatment, inspect uncertainty and assignment balance, and calculate sample-size plans.
4. **Investigations:** compare March 1–7 with March 8–14, 2026. Explore conversion, revenue, or active-user contributions by segment.
5. **Overview:** inspect growth/revenue and run local churn-model evaluation.
6. **Evaluation:** run the 58 reference-query cases. Leave model baselines unchecked unless Ollama is available. The score describes those cases on that database, not arbitrary-query accuracy.
7. **Settings / Schema Explorer:** upload or select a SQLite database and inspect its schema.

The generator includes a predefined synthetic treatment effect. Older existing demo databases are preserved and may not contain that newer effect. To create a separate fresh demo without overwriting your data:

```powershell
.\.venv\Scripts\python.exe scripts/generate_dataset.py --output datasets/fresh-demo.db
```

Choose a filename that does not already exist, then select it in Settings.

## Optional Ollama

Install Ollama separately, then run:

```text
ollama pull qwen2.5-coder:1.5b
ollama serve
```

If Ollama is already running, a second `serve` command is unnecessary. Its absence is shown as Offline mode; it does not prevent supported offline analysis.

## Configuration

Defaults work without an environment file. Optionally copy `.env.example` to `.env` in the repository root. Relative database paths resolve from the repository root, including when the backend starts from its own folder. Environment variables override the file. Never commit secrets or uploaded customer data.

The default development mode binds only to `127.0.0.1`. Everyone running a separate clone has their own local workspace. The production gateway configuration is optional infrastructure for hosted deployments, not required for this project demo. Do not expose the development servers to the internet.

## Tests

Windows:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest
Set-Location ../frontend
npm exec --yes --package=pnpm@11.25.0 -- pnpm test
npm exec --yes --package=pnpm@11.25.0 -- pnpm run lint
npm exec --yes --package=pnpm@11.25.0 -- pnpm run build
```

For an exported benchmark report, from repository root:

```powershell
.\.venv\Scripts\python.exe scripts/run_benchmark.py --output logs/my-benchmark.json
```

The report filename must not already exist. Add `--include-models` to measure available Ollama baselines. No scores are fabricated for unavailable models.

## Troubleshooting

- **Python, node, or npm not recognized:** install the prerequisites and reopen your terminal. The project does not depend on Codex runtime paths.
- **Missing .venv or scripts:** change to the repository root and run setup. Do not run from `C:\Users\your-name`.
- **Port 8000 or 5173 occupied:** stop your previous VEYRA terminal with Ctrl+C, or identify the other application. The launcher refuses to reuse unrelated services.
- **Dependency download fails:** check your connection/proxy and rerun setup; completed installation steps can be reused.
- **Locked SQLite file:** stop the app before regenerating a database. Prefer a new demo filename. Avoid running the working database inside a synchronization folder.
- **A custom database cannot run product metrics:** Ask Veyra discovers different SQLite schemas, but trusted analytics require compatible product tables. The app lists missing fields instead of guessing meanings.

## Scope and documentation

To test unfamiliar schemas and prepare verified model examples, see [dataset generation and learning](docs/dataset-learning.md). This includes five synthetic databases, 32 diagnostic cases, and schema-family-separated example exports; no model training is required.

The reliability work is tracked in the [incremental implementation plan](docs/improvement-plan.md). See the [benchmark audit](docs/evaluation-audit.md) and [independent 108-case evaluation methodology](docs/independent-evaluation.md) for new structurally different fixtures, strict system comparisons and evaluation-exposure limitations.

The [108-case failure analysis](docs/failure-analysis-v1.md) documents confirmed causes, evaluation weaknesses and the proposed next changes. Those reviewed cases are now development-exposed, not an untouched final test set.

The [first compositional planner increment](docs/compositional-planner-v1.md) implements structured filters/groupings, foreign-key normalization and SQL coverage checks. It reports development improvements, regressions, supported operations and a separately reserved, unscored final artifact.

The [relationship-existence increment](docs/existence-planner-v1.md) adds bounded correlated EXISTS/NOT EXISTS, improving development exact results from 48/90 to 57/90 with no previous-pass regressions. The reserved final archive remains unopened and unscored.

The [temporal and distinct-activity increments](docs/temporal-activity-increments.md) add validated timestamp relationships and distinct observed identities, reaching 64/90 exact development results and 82/108 overall outcomes with no previous-pass regressions. The report documents UTC/NULL semantics, tests, and remaining unsupported operations; these are not held-out results.

Additional [synthetic stress testing](docs/synthetic-stress-v1.md) runs 90 new question formulations against paired rental, support and billing fixtures. It exposes five wrong-answer formulations not caught by the original suite; no planner changes or held-out claims are made by that testing increment.

The subsequent [interpretation-grounding fixes](docs/interpretation-grounding-v1.md) correct those five wrong-answer formulations and three distinct-ID clarifications per variant: 50/78 exact synthetic results, with no previous-pass regressions. A [dataset context brief](docs/dataset-context-template.md) explains what definitions and mappings an analyst can provide; it is not yet an automatically applied semantic-layer configuration.

The [two-source context demo](docs/joined-context-demo.md) provides synthetic CRM/product databases, a combined upload-ready snapshot, a completed context brief and recorded query results. It tests joins inside one snapshot, not two-file federation or automatic context ingestion, and documents a newly exposed UTC-boundary error.

You can now [combine 2–5 uploaded SQLite sources inside Settings](docs/multi-source-snapshots.md): explicitly map cross-source keys, create/review a new namespaced snapshot, then connect it for queries. Sources stay unchanged. This is a static snapshot, not live federation or automatic semantic-context ingestion.

SQLite is the implemented database adapter. Metrics use UTC and explicit definitions. Investigations are descriptive, not causal proof. Predictive scores are historical synthetic-data evaluations, not evidence of real-product forecasting quality.

The [corrected-query stress report](docs/corrected-query-testing-v1.md) documents 400 development case executions, numeric field-binding and punctuation fixes, unchanged-denominator measurements and remaining unsupported wording.

See [architecture](docs/architecture.md), [schema](docs/database-schema.md), [metrics](docs/metrics.md), [experimentation](docs/experimentation.md), [investigations](docs/investigations.md), [evaluation](docs/evaluation.md), and [release status](docs/release-status.md).

For a future hosted service, see [production readiness](docs/production-readiness.md). Multi-customer isolation, identity integration, deployment verification, and backup/restore operations remain outside the local-project quick start.

