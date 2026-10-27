# Compositional planner: first increment

## Outcome and scope

Implemented a bounded structured planning path for unfamiliar SQLite schemas, beginning with filters, grouping and foreign-key normalization. This replaces raw-table fallback on the new path, not the existing product-metric mathematics. The original 108-case manifest and databases are unchanged and remain development-exposed.

| Offline development metric | Original | This increment |
|---|---:|---:|
| Exact query results | 22/90 (24.4%) | 48/90 (53.3%) |
| Overall labeled outcomes | 37/108 (34.3%) | 66/108 (61.1%) |
| Executed query targets | 65/90 | 48/90 |
| Wrong executed query targets | 43 | 0 |
| Unnecessary clarifications on query targets | 17 | 42 |
| Correct clarification labels | 9/12 | 12/12 |
| Clarification precision | 9/26 (34.6%) | 12/54 (22.2%) |
| Write-request refusals | 6/6 | 6/6 |
| Exceptions | 9 | 0 |

**31 previous failures fixed, two previous passes regressed, 35 passes retained, 40 failures retained.** The two regressions (`education-05`, `collaboration-05`) are the audit's accidental-pass cases: total-person counts coincided with participating-person counts. This version withholds those unsupported participation queries instead of restoring the logically incorrect counts. They still count as regressions under the unchanged evaluation contract.

The new path is substantially more conservative: it withholds 42 answerable queries. Zero wrong executed answers on these fixtures is not universal correctness, and lower execution coverage must not be hidden behind accuracy. Improvements are measured development results, **not held-out generalization**. No new full-model accuracy comparison or model training was performed.

## Architecture

### Request representation

`CompositionalQuery` is a versioned Pydantic representation exposed through the optional `QueryPlan.composition` field. It contains:

- Entity/fact table and count/sum/average measure with an optional distinct key.
- Typed column predicates, operators and literal values, separate from presentation strings.
- Multiple grouping fields and an optional daily grain.
- Date-field roles with explicit start and exclusive end constraints.
- Join equalities and foreign-key constraint identity.
- Distinctness, ranking descriptors, limits, requested operations and unresolved operations.

The model can represent ranking and limits, but this first natural-language parser deliberately withholds unresolved rankings/tie rules. A representation field does not imply that every way to request that operation is implemented.

### Grounding, compilation and coverage

The planner still uses bounded lexical evidence to ground identifiers; it is not a learned semantic parser. Unlike the prior path, SQL generation consumes the structured representation rather than directly mixing a selected table with a few keyword conditions. Measures and dimensions can come from different tables, numeric/null predicates are explicit, and unknown content terms or unsupported operations trigger clarification.

Compilation quotes identifiers and escapes string literals. Numeric thresholds, multiple supported threshold predicates, null/non-null checks, approved categorical equalities, count/sum/average, basic distinct entity counts, multiple dimensions, daily grouping, simple calendar windows and forward foreign-key joins are supported. Explicit numeric row-list limits from 1 to 5,000 are honored; invalid limits, unbound numeric qualifiers and reversed date windows are withheld. Average results retain computation precision rather than being rounded to two decimals.

Coverage checks compare SQLGlot ASTs against the structured contract, including Boolean predicate structure, literal/date boundaries, grouping, projection/measure, join conditions, distinctness, order and limit. Extra unplanned clauses are rejected too. Mutation tests remove or change predicates, groups, dates, relationships, limits, order and measures; all must be withheld.

The comparison is intentionally conservative: it is **not a general SQL equivalence prover**. Even an equivalent model rewrite with a different AST may be withheld. Recognized requests are checked against SQL; no claim is made that the bounded parser recognizes every natural-language operation.

### Integration and safety boundaries

Known canonical templates and analytical modules remain in place. Canonical simple templates with additional supported predicate/grouping requests are routed to the structured path to avoid swallowing those operations. Legacy canonical templates do not all receive a compositional representation; their existing contracts and regression tests remain a separate boundary.

Model-generated replacements for a structured query must satisfy the same coverage check before execution. SQLGlot identifier/read-only validation, SQLite read-only URI mode, authorization, SQL limits, response bounds and execution deadlines remain independent safeguards. Coverage mismatch returns a clarification rather than executing the weaker query.

The UI provides an expandable structured-plan inspector on successful structured queries. Existing clients can ignore the additive field.

### Foreign-key normalization and grain

Discovery is now two-pass: read table metadata, then resolve omitted referenced columns using the ordered declared primary key. Foreign keys retain constraint ID and sequence; composite joins include all equality terms. Unresolvable keys are not guessed.

Join grounding distinguishes parallel roles when the request identifies them (for example destination_depot rather than origin_depot). Equally likely roles produce clarification. Reverse joins that would expand the fact grain are withheld pending explicit preaggregation/distinct-entity support; no uncontrolled fanout is introduced.

The static bounded category profiler now also recognizes state, stage and role. Existing sensitive-name filtering, sample/column/value limits remain. Arbitrary label/free-text columns are not broadly enabled.

## Actual before/after examples

These are abbreviated views of plans exported in `logs/compositional-v1-comparison-verified.json`.

### Education: “List completions with scores at least 50”

Before: a raw completion lookup with no threshold.

After:

```json
{
  "entity": "completions",
  "measure": null,
  "filters": [{"field": {"table": "completions", "column": "score"}, "operator": "gte", "value": 50.0}],
  "groupings": [], "dates": [], "joins": [],
  "distinct": false, "ranking": [], "limit": 5000,
  "requested_operations": ["filters"], "unresolved_operations": []
}
```

```sql
SELECT "completions".* FROM "completions"
WHERE "completions"."score" >= 50.0 ORDER BY 1 LIMIT 5000
```

### Logistics: “Parcel counts by destination zone”

Before: `NoneType.replace` during join construction.

After: entity `parcels`; measure COUNT; group `depots.zone`; explicit join `parcels.destination_depot = depots.depot_id`. The primary key is resolved from the declaration, and role evidence selects destination instead of the first foreign key.

```sql
SELECT "depots"."zone" AS "dimension", COUNT(*) AS "record_count"
FROM "parcels" JOIN "depots"
  ON "parcels"."destination_depot" = "depots"."depot_id"
GROUP BY 1 ORDER BY 2 DESC LIMIT 5000
```

### Collaboration: “Average paid invoice amount in USD cents”

Before: rounded AVG over every invoice, including void invoices.

After: entity `invoices`; measure AVG(invoices.usd_cents); predicate invoices.state = paid; no unresolved operations.

```sql
SELECT AVG("invoices"."usd_cents") AS "average_usd_cents"
FROM "invoices" WHERE "invoices"."state" = 'paid'
```

## Verification

- Starting baseline: 72 backend tests and three frontend tests passed.
- Foreign-key-only stage: one intermittent Windows rename failure was exposed. The shared test fixture used SQLite's transaction context without closing its connection; it now explicitly closes it. Result cursors are also explicitly closed on bounded read-only execution.
- Structured-path stage: old cross-schema tests caught nine compatibility regressions; grouping identifier preference, ordinary aggregate grammar and overlapping table-name handling were corrected. The original benchmark caught 20 legacy event-phrase regressions caused by an overbroad “where” routing guard; the established phrase was preserved. These intermediate failures are not hidden or called passing runs.
- Final: **115 backend tests passed**, including representative education/logistics/collaboration operations, implicit/composite keys, role ambiguity, fanout refusal, SQL mutation coverage, explicit/invalid limits, reversed date windows, unsupported operations and a model dropping a filter. One existing Starlette/httpx deprecation warning remains.
- **Three frontend tests passed**, TypeScript compiled, Vite built, and ESLint completed successfully. Vite warns about a large bundle; packaging/performance work is not finished.
- Original reference benchmark: **58/58**. The existing 32 cross-schema development cases remain **32/32**, also exercised by the backend suite.

## Frozen final artifact — not scored

After production-source implementation/testing was frozen, a separate archive was generated: **`evaluations/reserved-final-v2.zip`**, with a companion receipt. It contains **36 cases across two new schemas**. The generator independently computes Python answers and verifies reference SQL internally, but prints only receipt metadata. Neither answer files nor model/system responses were opened or used for debugging. No Veyra evaluation has run against it. The prior v1 reservation was retired, without opening it, after an implementation review added numeric-limit and reversed-window coverage; it remains recoverable on disk. v2 is the active final reservation.

Archive SHA-256: `717f40669f4596735911a560c4722a8d0870e4e01d34fd4ee42d761319ac7368`.

Production-source freeze SHA-256: `ada395bc800db09000ecb8357ecdfc4d37982d21c6f2b036a8f1a4f790b5f32a`.

This is internally authored and not externally blinded, encrypted or access-controlled. Its source necessarily contains question/reference construction logic. “Untouched” here means no answer-file inspection, system scoring or case-feedback-driven tuning after reservation; not absence of author knowledge. Keep the archive out of training/examples and do not unpack it during further development. Before final testing, agree acceptance criteria, record the final code/prompt freeze and any post-reservation changes, and explicitly release it. Inspection/tuning retires its untouched status. Generated archives/receipts are ignored by Git and need private artifact backup if moving machines.

## Reproduce development comparison

```powershell
.\.venv\Scripts\python.exe scripts/run_independent_evaluation.py --systems deterministic --output logs/my-composition-run.json
.\.venv\Scripts\python.exe scripts/compare_development_reports.py --after logs/my-composition-run.json --output logs/my-composition-comparison.json
.\.venv\Scripts\python.exe scripts/run_benchmark.py --output logs/my-canonical-regression.json
```

Comparison checks the unchanged manifest fingerprint and all 108 IDs, reports fixed/regressed cases and exports actual before/after examples. Historical baseline: `logs/independent-v1-deterministic.json`. Current report: `logs/compositional-v1-development-verified.json`. Output filenames must be new.

## Remaining work

Ordered funnels/ratios, anti/semi-joins, HAVING, complex distinct participation, normalized event-catalog grounding, NL ranking/tie handling, Boolean OR/negation and ambiguous/multiple timestamp roles remain unsupported in this path. They are withheld, not silently simplified. No approved semantic mapping UI/persistence is implemented. Full model-only/hybrid evaluation remains pending. Extend the planner on development fixtures, preserve the original denominator, and leave the reserved final artifact closed until ready.
