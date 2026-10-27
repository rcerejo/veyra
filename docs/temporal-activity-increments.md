# Temporal relationships and distinct activity: verified development increments

## Scope and architecture

Two bounded extensions build on the existing structured query planner and compiler. They do not replace the query engine, change public endpoint contracts, relax SQLGlot/read-only enforcement, or introduce arbitrary model SQL execution. Existing AST coverage validation remains mandatory. Unresolved operations still produce clarification.

1. **Temporal relationships:** typed inner date windows and outer/inner timestamp comparisons inside correlated EXISTS/NOT EXISTS. Timestamp roles must be explicit or unique. A narrowly grounded categorical fact can identify the related table only when its value identifies one table and the existing relationship planner resolves its keys.
2. **Distinct observed activity:** typed source, identity and entity metadata; COUNT(DISTINCT observed identity), optional daily/weekly grouping, and explicit date/event filters. Identity resolution follows actual outgoing foreign keys, at most two edges. Ambiguous sources or identity roles are withheld. Registered populations and event-row counts are not substitutes for active identities.

Main changes: `backend/app/schemas/query.py`, `backend/app/query_engine/compositional.py`, `relationships.py`, new `temporal.py`, new `activity_planner.py`, and service-boundary timestamp validation in `service.py`. Frontend API types are additive; the existing query-plan inspector can display the metadata. No new onboarding or dashboard feature is claimed.

## Representative plans

Previously these operations were withheld; the examples below show abbreviated structured intent, not new benchmark labels or universal language coverage.

```text
Count parcels delivered on or after their shipping date
  outer: parcels; measure: count rows
  existence: checkpoints; filter: delivery category = delivered
  correlation: checkpoint parcel key = outer parcel key
  comparison: checkpoint timestamp >= outer shipping timestamp
  missing outer anchor: exclude

Weekly distinct actors from activity records during March 2026
  source: resolved activity fact table
  measure: count distinct resolved actor foreign key
  group: fact timestamp, week (Monday start, UTC)
  window: [2026-03-01, 2026-04-01)
  unknown fact date: exclude
```

Actual case plans and generated SQL are preserved in `logs/temporal-v1-comparison.json`, `logs/activity-v1-comparison.json`, and `logs/platform-increments-comparison.json`.

## Temporal and identity contracts

- Calendar windows are UTC, normally half-open. Explicit inclusive end dates become the following midnight. Strict timestamp comparisons retain their requested operator.
- Relative last-N-day windows mean previous complete UTC calendar days, excluding today; supported N is 1–366. Weeks start Monday. Tests inject the clock. Rolling-hour interpretation is not silently substituted.
- ISO offsets normalize through SQLite JULIANDAY/DATE. Naive ISO timestamps are treated as UTC. Epoch numbers, invalid calendar dates, and unrecognized local/mixed representations are withheld.
- Every relevant timestamp column is checked across the whole column, not just the profile sample, under a two-second read-only deadline. This adds scan cost; large databases may receive clarification when validation cannot complete. A validated persisted timestamp contract would be a future optimization.
- Missing relationship anchors are excluded explicitly even for NOT EXISTS; missing inner timestamps do not satisfy temporal predicates. This avoids treating an unknown anchor as evidence of no qualifying activity.
- NULL identities do not contribute to distinct counts. Unknown dates do not create calendar buckets. Weekly distinct identities are counted across the week, not summed from daily distinct counts.
- Generic “active” is not automatically interpreted as a categorical `state = active` filter. No conversion denominator or business definition is invented.

SQLite timestamp precision and supported ISO syntax remain limitations; this is not a general timezone/business-calendar engine. Composite activity identities, arbitrary identity paths, ordered stages, and compound relationship requests are not enabled by this increment.

## Measured results

Same unchanged 108 development-exposed cases, including 90 answerable queries, 12 clarification labels and six invalid requests. Deterministic pipeline only; these are not new Ollama or hybrid model measurements.

| Metric | Starting existence planner | Temporal increment | Activity increment |
|---|---:|---:|---:|
| Exact query results | 57/90 (63.3%) | 60/90 (66.7%) | 64/90 (71.1%) |
| Executed query targets | 57/90 | 60/90 | 64/90 |
| Correct overall outcomes | 75/108 (69.4%) | 78/108 (72.2%) | 82/108 (75.9%) |
| Unnecessary clarifications | 33 | 30 | 26 |
| Wrong executed answers | 0 | 0 | 0 |
| Exceptions / unsafe attempts | 0 / 0 | 0 / 0 | 0 / 0 |
| Previous-pass regressions | — | 0 | 0 |

Temporal support fixes education-26, education-30 and logistics-26. Activity support fixes education-17, logistics-16, collaboration-15 and collaboration-29. Seven previous failures fixed; all 75 initially correct outcomes retained. All 12 expected clarifications and six refusals remain correct. Zero wrong executed answers is a fixture-specific observation, not a correctness guarantee for unfamiliar customer data.

## Verification

Backend tests: 160 starting, 195 after temporal support, **214 after activity support**. Added tests cover date boundaries, NULL anchors, offsets, invalid dates beyond the first 1,000 rows, relative clock windows, duplicates, registered-versus-observed identities, two-hop identity resolution, ambiguous sources/roles, and unsupported requests. Mutation tests remove or alter comparisons, NULL exclusions, DISTINCT, identity columns, filters and grouping grains; coverage must reject them. Service tests reject substituted model SQL and invalid timestamp data.

Frontend: **3 tests passed**, TypeScript and ESLint passed. Canonical **58/58** and existing cross-schema **32/32** passed after each increment. One existing backend Starlette/httpx deprecation warning remains.

## Remaining limitations and priorities

All 26 remaining incorrect development outcomes are withheld answerable requests, not wrong executions. Primary capability labels (manual, not proof of a single root cause): ordered funnels/ratios 7; normalized event catalogs 5; ranking 3; grouped relationship HAVING 3; advanced existence 2; distinct identity/source grounding 2; parallel join roles 1; related timestamp role 1; measure wording 1; grain qualifier 1. Details: `logs/platform-increments-remaining.json`.

Next implement normalized catalog-to-fact grounding with validated foreign keys and explicit identity/date roles, then ordered funnel stage contracts. Catalog grounding is foundational for several funnel requests; neither should be approximated with unordered event counts. Ranking/HAVING remain later work. No claim is made that all platform priorities or production deployment requirements are complete.

## Evaluation integrity and reproduction

All 108 cases are development-exposed. No held-out generalization claim is justified. Historical baseline files and development fingerprints are preserved; new reports use new filenames. Reserved final archives, receipts, answers and construction logic were not opened, executed, regenerated or used for implementation. Ordinary source fingerprinting reads script bytes without exposing final contents. Production source has changed since reservation; record a fresh code/prompt freeze and obtain explicit release before any final evaluation.

```powershell
.\.venv\Scripts\python.exe scripts/run_independent_evaluation.py --systems deterministic --output logs/my-temporal-activity-run.json
.\.venv\Scripts\python.exe scripts/compare_development_reports.py --before logs/existence-v1-development-final.json --after logs/my-temporal-activity-run.json --example-ids education-26 education-17 collaboration-15 --output logs/my-temporal-activity-comparison.json
.\.venv\Scripts\python.exe scripts/run_benchmark.py --output logs/my-temporal-activity-canonical.json
.\.venv\Scripts\python.exe scripts/evaluate_dataset_pack.py --output logs/my-temporal-activity-old32.json
```

Choose unused output names. Final artifacts: `logs/temporal-v1-development-verified.json`, `logs/activity-v1-development-verified.json`, both increments' `canonical58` and `old32` reports, `logs/platform-increments-comparison.json`, and `logs/platform-increments-remaining.json`. The remaining-capability report compares against the earlier 48/90 compositional baseline; the platform comparison explicitly compares this turn's 57/90 starting point to 64/90.

Legitimate resume wording: “Extended a structured analytics query planner with temporal relationship predicates and distinct activity metrics; increased exact results from 57/90 to 64/90 on a development-exposed cross-schema evaluation, with no prior-pass regressions.” Do not describe this as held-out accuracy, customer adoption, model training or production deployment.
