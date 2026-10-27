# Interpretation grounding fixes: numeric equality and distinct identities

## Implemented scope

This increment fixes the two wrong-answer families confirmed by synthetic stress testing. Production changes are confined to `backend/app/query_engine/compositional.py`; the structured representation, compiler, SQLGlot validation, read-only adapter, coverage checks and clarification boundaries remain in use. No model was trained and no semantic-mapping persistence/UI was introduced.

### Typed scalar equality

Previously, explicit equality captured a word as text regardless of the declared column type. `fee is zero` compiled as `fee = 'zero'`. Equality values now resolve using the declared type: unquoted zero through ten become numeric values only for numeric columns; integer, finite decimal and scientific literals are parsed as numbers. Non-numeric text descriptions and quoted number words on numeric fields trigger clarification; oversized SQLite integers and non-finite floats are withheld. Numeric-looking quoted literals such as `"0"` are accepted as numbers for numeric columns. Text columns retain text, including case and quoted multiword values.

The parser also masks values already bound to explicit fields before category-profile matching. A numeric `fee is zero` must not additionally invent `label = 'zero'` just because an unrelated label column contains that word. Repeated explicit equalities on one field are withheld rather than dropping one. Unknown number phrases such as “one hundred” remain unsupported, not approximated as one.

### Requested distinct identity

Previously, generic distinct requests unconditionally chose the source table primary key. The planner now binds an exact field/role (including a qualified source field) or an unambiguous declared foreign-key entity relationship. The primary key is used only when the requested entity is the source entity itself and there is one primary-key column.

Examples:

```text
Before: Count distinct inspectors from inspections
  measure = COUNT(DISTINCT inspections.inspection_id)    # wrong row identity
After:
  measure = COUNT(DISTINCT inspections.inspector_id)     # requested role

Before: Count bookings where fee is zero
  filter = fee eq "zero"                                # text
After:
  filter = fee eq 0                                     # integer
```

Explicit FK identity counts no longer require an unnecessary join to the parent table merely because the key name resembles that table. “Distinct people” remains ambiguous when inspector and reviewer both reference people. Unknown identities, multi-field distinct requests, unsupported composite entity identities and foreign qualified fields are withheld, not replaced by source-row IDs. This remains a bounded grammar, not complete language understanding.

## Measured results

Same frozen 90 synthetic question formulations and same two database variants, with 78 answerable queries per variant. Both variants have identical classifications before and after:

| Metric per variant | Before | After |
|---|---:|---:|
| Exact query results | 42/78 (53.8%) | 50/78 (64.1%) |
| Executed answerable queries | 47/78 (60.3%) | 50/78 (64.1%) |
| Correct overall outcomes | 54/90 (60.0%) | 62/90 (68.9%) |
| Unnecessary clarifications | 31 | 28 |
| Wrong executed answers | 5 | 0 |
| Exceptions / unsafe attempts | 0 / 0 | 0 / 0 |
| Previous-pass regressions | — | 0 |

Eight failures fixed per variant: rentals-10/19/25/26, support-10/19 and billing-10/19. Five were wrong executions and three were unnecessary distinct-ID clarifications. Expected clarification labels remain 6/6 and write refusals 6/6. Paired runs are 100/156 exact query results and 124/180 overall outcomes; the variants repeat questions and do not constitute 180 independent linguistic cases.

The original development evaluation remains **64/90 exact and 82/108 overall**, with zero wrong executions and zero previous-pass regressions. Canonical **58/58** and prior cross-schema **32/32** remain intact. These exposed development fixtures do not establish held-out generalization, and zero wrong executions on these cases is not a guarantee for other questions.

## Tests and boundaries

**262 backend tests passed**, versus 220 before changes; **three frontend tests**, TypeScript and ESLint passed. The 42 new tests exercise numeric words/literals, decimal/exponent/sign handling, text case and type preservation, cross-column category collisions, role identities, NULL/duplicate IDs, qualified identifiers, ambiguous roles, unsupported requests and SQL mutations. A service-level model replacement using the wrong primary key is withheld by coverage validation. One existing Starlette/httpx deprecation warning remains.

28 answerable synthetic requests per variant remain withheld. Known gaps include daily/UTC/NULL phrasing, NULL foreign-key requests, relationship wording, joined grouping, ranking, HAVING, composite/catalog grounding and ordered funnels. The synthetic report's previous five incorrect formulations are fixed, not evidence that all interpretation issues are solved. Next audit the remaining representable-but-withheld requests and implement an approved semantic vocabulary/mapping contract incrementally; do not relax coverage to force more execution.

## Context users can provide

The most useful context is a reviewed **data dictionary and metric contract**, not a large dump of raw records: row grain, actual entity identity, exact relationship roles, human event synonyms, date/time conventions, units/currencies, qualifying activity and denominators, plus representative questions and approved reference answers where available. See `docs/dataset-context-template.md`.

That template is a human-readable brief, not a new accepted API input or automatically applied mapping. Existing semantic-layer documentation remains a design contract; persistence, schema-bound validation/versioning, approval and runtime mapping application are still future work. Users should not have to repeat established business definitions in every question once such a workflow exists. Even complete context cannot guarantee perfect interpretation; ambiguous choices must still be surfaced.

## Artifacts and reproduction

New verified reports: `logs/interpretation-v1-seed11-verified.json`, `logs/interpretation-v1-seed29-verified.json`, `logs/interpretation-v1-diagnostics.json`, `logs/interpretation-v1-original108-verified.json`, `logs/interpretation-v1-original108-comparison.json`, `logs/interpretation-v1-canonical58.json`, and `logs/interpretation-v1-crossschema32.json`. Intermediate reports without the `verified` suffix predate the last FK-binding fix; use verified reports for final results.

```powershell
.\.venv\Scripts\python.exe scripts/run_independent_evaluation.py --pack datasets/evaluation/synthetic-stress-v1-seed11 --systems deterministic --output logs/my-grounding-seed11.json
.\.venv\Scripts\python.exe scripts/run_independent_evaluation.py --pack datasets/evaluation/synthetic-stress-v1-seed29 --systems deterministic --output logs/my-grounding-seed29.json
.\.venv\Scripts\python.exe scripts/run_independent_evaluation.py --systems deterministic --output logs/my-grounding-original108.json
.\.venv\Scripts\python.exe scripts/run_benchmark.py --output logs/my-grounding-canonical58.json
.\.venv\Scripts\python.exe scripts/evaluate_dataset_pack.py --output logs/my-grounding-crossschema32.json
```

Output names must be new. All historical snapshots/reports remain preserved. Reserved final archives, receipts, answers and construction logic were not opened, regenerated, executed or used for development. Normal source fingerprinting hashes script bytes without exposing final answers. No model-only/hybrid score, production deployment or customer adoption claim is made.
