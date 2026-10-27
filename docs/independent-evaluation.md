# Independent evaluation v1

## Status and scope

**Current role: development.** All 108 cases have been reviewed for debugging/failure analysis. They are no longer eligible for held-out claims. `evaluation-registry.json` supersedes original manifest/report exposure labels without changing the frozen fixture hashes. See [failure analysis](failure-analysis-v1.md) and the later [compositional increment](compositional-planner-v1.md), which records a separate unopened internal final reservation, not scored final performance.

This is an internally authored synthetic baseline kept separate from development examples, not an externally blind benchmark. The cases are new relative to the 58 canonical development regressions, 32 cross-schema diagnostics and commerce/support training exports. Production generation code was not changed to fix these new cases. Do not add these cases to retrieval examples or regression-driven planner tuning while calling the results held-out.

The fixture author and system author are the same agent. Human review of business wording and labels, more data seeds, and an externally authored final set remain desirable. Once failures are used for debugging, update the exposure designation and use a newly frozen suite for final claims. Case hashes and source hashes identify a run; they do not prove an absence of prior exposure.

## Data and questions

Three SQLite schemas, 36 questions each, 108 total:

- **Education:** learners, courses, enrollments, lesson views and completions; learner-course enrollment relationships, nullable scores and date-ordered completion funnels.
- **Logistics:** depots referenced twice in different roles, parcels, composite-key checkpoints and a one-to-many multi-currency charge ledger with refunds. Tests role ambiguity, fanout, currency and ordered delivery funnels.
- **Collaboration:** people and organizations connected through a composite-key membership bridge, normalized action catalog, audit log and invoices. Tests distinct users across organizations, membership versus activity, event-catalog joins and person-level funnels across workspaces.

There are 90 query targets, 12 clarification targets and six invalid write-request targets. The question set includes simple counts/filters, joins, grouped sums, date boundaries, nulls, distinct users, rankings with tie rules, HAVING, anti-joins, missing fields, undefined business definitions and ordered funnels. Some question structures recur across domains: 108 questions are not 108 unique reasoning patterns.

Each query's expected answer is computed using Python tuples, comprehensions, sets and grouping, separately from SQLite. Before scoring, the evaluator validates and executes every reference query and requires agreement with that oracle. Database fingerprints must match. Authoring-stage reference issues were corrected before any generation scoring: duplicate origin/destination column labels were given unique aliases, and correlated fixture cycles were adjusted to exercise nontrivial cross-course and event funnels. These were fixture-quality checks, not planner changes from final-case failures.

Funnel questions here explicitly permit same-day steps and state their denominators. They test the SQL query engine, not parity with the product Funnel module, whose existing contract uses strictly increasing timestamps and mature windows. No implicit definition is shared between those workflows.

## System comparison

| System | Generation | Model fallback | Corrections |
|---|---|---|---|
| deterministic | Existing canonical compiler and schema-derived semantic planner | Disabled | None |
| ollama_only | Schema/profile plus question, structured query/clarification/refusal output | Never | None |
| hybrid | Existing QueryService, including clarification gates and schema subset selection | Model preflight required; runtime model failure is an error | Existing maximum two model corrections |

All systems use the same database snapshots, bounded schema/value discovery, read-only SQL validation, 5,000-result-row limit and eight-second SQL execution timeout. Training/retrieval examples are disabled. Gold SQL, expected outcomes and oracle rows are never supplied to generation. Preflight requires an exact installed model name (or its implicit `:latest` tag), and the report records the model digest when available. Missing models are skipped, never replaced by offline results in model-only mode.

This compares actual systems, not identical prompts: Ollama-only sees the complete discovered schema, hybrid may select a subset and has planner gates/correction attempts. Report those advantages and costs. Temperature is zero, each model HTTP request has a 45-second timeout, and no fixed-seed determinism or total-request-time equality is claimed. System order is recorded. Warm-up and local resource contention are uncontrolled, so latency is descriptive, not a controlled speed benchmark.

## Metrics

- **Execution success:** executed responses divided by answerable query cases. Execution is not correctness.
- **Exact result correctness:** complete matching answers divided by query cases, including failures and unnecessary clarifications in the denominator.
- **Labeled outcome accuracy:** correct query results, correct clarification labels and correct refusal labels divided by all measured cases.
- **Clarification recall:** clarification responses on clarification targets divided by clarification targets.
- **Clarification precision:** correct clarification labels divided by all clarification responses.
- **Refusal accuracy:** explicit refusals divided by invalid-request cases. An unsafe SQL attempt blocked by the validator is not credited as correct intent handling.
- **Error rate:** exceptions/unsafe attempted queries divided by measured cases. Ordinary wrong results and unnecessary clarifications are tracked separately, not mislabeled as execution errors.

The report includes all metrics by schema and complexity with counts. Clarification scoring checks the response category, not whether the follow-up wording asks the right business question. SQL aliases are ignored; duplicate rows are preserved. Ranked questions require ordered rows. Other questions compare multisets, with numeric tolerance of 1e-7 absolute / 1e-9 relative. Truncated answers never count as correct.

## Reproduction

From the repository root in Windows PowerShell:

```powershell
# Creates a new frozen directory; refuses to overwrite.
.\.venv\Scripts\python.exe scripts/build_independent_suite.py

# Verify reference SQL against Python answers, without scoring generation.
.\.venv\Scripts\python.exe scripts/run_independent_evaluation.py --verify-only

# Full offline baseline; choose a new report name for every run.
.\.venv\Scripts\python.exe scripts/run_independent_evaluation.py --systems deterministic --output logs/independent-offline.json

# Full three-system comparison. Requires an installed model; CPU runs may be slow.
.\.venv\Scripts\python.exe scripts/run_independent_evaluation.py --model llama3.1:8b --output logs/independent-all-systems.json
```

Use `--output <new-directory>` for a second fixture generation and `--pack <that-directory>` for evaluation. `--limit` or `--case-ids` selects a partial run and marks the report partial. A stratified pilot selected the first count, a join, an ordered funnel, a missing/ambiguous-field question and a write request from each schema:

```powershell
.\.venv\Scripts\python.exe scripts/run_independent_evaluation.py --case-ids education-01 education-18 education-27 education-32 education-35 logistics-01 logistics-18 logistics-27 logistics-32 logistics-35 collaboration-01 collaboration-18 collaboration-27 collaboration-32 collaboration-35 --output logs/independent-stratified-pilot.json
```

Reports include full case outcomes, complexity/schema aggregates, manifest and database fingerprints, source-file fingerprints, model identity, runtime and selected settings. A result with `partial: true` is not a 108-case score, even if all selected cases were measured. Generated datasets/reports stay local and are excluded from Git; the generator and methodology are source-controlled candidates. Run filenames refuse overwrite.

Harness tests use separate toy fixtures, including unavailable models, unsafe model output, oracle disagreement, fingerprint changes, duplicate preservation, ordered results and clarification denominators. They do not assert that the production planner answers final-suite questions correctly.

See `independent-evaluation-results.md` for the observed results and `evaluation-audit.md` for the previous suites' limitations.
