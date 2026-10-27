# Bounded relationship-existence increment

## Findings and selected extension

Reviewed the architecture, first compositional report, planner/compiler, validator, service and tests before modifying generation. The starting 108-case development run contained 48/90 correct query answers and 66/108 correct overall outcomes; all 42 failed query targets were withheld, with zero incorrect executed answers. Baseline verification: 115 backend and three frontend tests passed.

Manual capability classification of the 42 withheld questions:

| Missing capability | Before | Fixed here | Remaining |
|---|---:|---:|---:|
| Bounded foreign-key existence/absence | 9 | 9 | 0 |
| Advanced existence conditions | 5 | 0 | 5 |
| Ordered funnels and ratios | 7 | 0 | 7 |
| Distinct activity/entity grounding | 6 | 0 | 6 |
| Normalized event catalogs/fact-table grounding | 5 | 0 | 5 |
| Ranking and ties | 3 | 0 | 3 |
| Grouped relationship HAVING | 3 | 0 | 3 |
| Parallel role aliases | 1 | 0 | 1 |
| Date role on a related table | 1 | 0 | 1 |
| Measure wording | 1 | 0 | 1 |
| Grain-related qualifier interpretation | 1 | 0 | 1 |
| **Total** | **42** | **9** | **33** |

Existence is the largest broad family (14), but five require more than a basic existence operator: three temporal cases, one compound existence request and one composite correlation without a direct entity-to-association FK. Counts classify the primary missing capability, not guaranteed single-cause fixes. IDs and measured transitions are recorded in `logs/existence-v1-operations-final.json`; `scripts/summarize_remaining_operations.py` checks that the labels exactly partition the original 42 failures.

The smallest useful extension is a typed **correlated EXISTS/NOT EXISTS predicate**. Ordinary joins can multiply outer rows; existence preserves each outer record regardless of how many related records match. This addresses more cases in one controlled family than ranking (3), HAVING (3) or event-catalog grounding (5), without implementing arbitrary join aggregates, funnels or new business metrics.

## Implemented architecture

- Added `QueryExistence` to the existing `CompositionalQuery`: inner entity, nonempty correlations, existing typed joins, existing typed filters, and negation. The frontend API type is additive; the existing plan inspector displays it automatically.
- Added a restricted relationship grammar in `query_engine/relationships.py`. It identifies explicit list/count/unique-count requests using with, have, belong to, without or with no. Unknown qualifiers are not discarded.
- Grounds entities against actual schema names, with bounded noun/verb morphology (for example enrolled/enrollment), not schema-specific aliases or evaluation IDs. Supported inner filters require the existing bounded safe category samples; profiling permissions were not widened.
- Discovers deterministic, bounded shortest FK paths (up to three edges, 1,000 path expansions, at most 20 candidate shortest paths). Equal paths/roles are not arbitrarily selected. All composite-key terms are retained. Broken referenced keys, self/repeated-table paths and alias-dependent requests are withheld.
- For “belong to,” a direct declared relationship or an unambiguous structural association bridge is required. A unique activity-only path is not treated as membership. Multiple eligible bridges still require clarification. This is bounded structural grounding, not a universal approved business semantic layer.
- Compiles inner joins inside EXISTS and outer/inner correlation predicates in WHERE. Reverse links are safe inside an existence subquery because their multiplicity does not change outer grain. The general planner's reverse-join/fanout restrictions remain unchanged.
- Reuses literal escaping, identifier quoting and the existing SQLGlot AST coverage contract. No alternate unsafe SQL execution path or model fallback was introduced.
- Adds inner tables to the query's relevant-schema context. A model-generated replacement still must preserve the complete structured SQL contract, including inner filters, correlations and negation.

SQLGlot validation, read-only SQLite execution/authorization, row/time limits and the existing canonical analytics remain in place. Unsupported compound, grouped, temporal, ranked or ungrounded relationship requests still return clarification. In this version, even a limit attached to the specialized relationship grammar is withheld rather than silently ignored.

## Examples from the measured development run

### Participating learners, not all registered learners

“How many different learners have enrolled?” now plans a distinct outer key and a positive correlated existence predicate:

```sql
SELECT COUNT(DISTINCT "learners"."learner_id") AS "record_count"
FROM "learners"
WHERE EXISTS (
  SELECT 1 FROM "enrollments"
  WHERE "enrollments"."learner_id" = "learners"."learner_id"
)
```

Previously this was withheld; the earlier legacy implementation had accidentally matched the expected count by counting all learners. New test data includes nonparticipating learners, duplicate enrollments, NULL links and orphan links, so that mistake can no longer pass the development regression test.

### Courses without any completions

The unique two-edge path is contained inside the correlated subquery:

```sql
SELECT "courses".* FROM "courses"
WHERE NOT EXISTS (
  SELECT 1 FROM "enrollments"
  JOIN "completions"
    ON "completions"."enrollment_id" = "enrollments"."enrollment_id"
  WHERE "enrollments"."course_id" = "courses"."course_id"
)
ORDER BY 1 LIMIT 5000
```

### Organizations with no paid invoices

The payment-state filter must be **inside** the absence condition:

```sql
SELECT "organizations".* FROM "organizations"
WHERE NOT EXISTS (
  SELECT 1 FROM "invoices"
  WHERE "invoices"."org_id" = "organizations"."org_id"
    AND "invoices"."state" = 'paid'
)
ORDER BY 1 LIMIT 5000
```

An organization with only void invoices qualifies; an organization with duplicate paid invoices does not. NULL child foreign keys do not incorrectly eliminate unrelated organizations, unlike a naïve NOT IN implementation.

## Measured before/after results

Same 108 case IDs, 90 query targets, unchanged database/manifest fingerprints and labels; offline deterministic/semantic mode, no examples or model generation.

| Metric | Previous increment | This increment |
|---|---:|---:|
| Exact query correctness | 48/90 (53.3%) | **57/90 (63.3%)** |
| Executed query targets | 48/90 (53.3%) | **57/90 (63.3%)** |
| Overall labeled outcomes | 66/108 (61.1%) | **75/108 (69.4%)** |
| Unnecessary clarifications | 42 | **33** |
| Wrong executed answers | 0 | **0** |
| Exceptions / unsafe attempts | 0 / 0 | **0 / 0** |
| Correct clarification labels | 12/12 | **12/12** |
| Write-request refusals | 6/6 | **6/6** |
| Clarification precision | 12/54 (22.2%) | **12/45 (26.7%)** |

**Nine previous failures fixed, zero previous passes regressed, all 66 correct outcomes retained.** Exact correctness improves by ten percentage points on this development set; overall correctness improves by 8.3 percentage points. These are not held-out generalization estimates and zero wrong executed answers is specific to these fixtures, not a universal correctness guarantee.

Fixed IDs: education 05/20/21, logistics 05/21/22, collaboration 05/21/22. The two participation questions withheld in the first compositional increment are now answered through real correlations, not restored incorrect all-person counts.

All 33 remaining incorrect outcomes are withheld answerable queries. No new error category was introduced. The table above details their primary unsupported capabilities.

## Verification

The targeted tests cover list/count/distinct-count existence, direct and multi-hop paths, composite keys, NULL and orphan foreign keys, duplicate child records, nonparticipants, filtered absence, explicit relationship roles, ambiguous paths/roles, competing association bridges, activity versus membership, ambiguous category fields, unresolved keys and unsupported compound/date/group/limit requests.

SQL mutation tests remove a correlation, turn it into a tautology or inner self-comparison, remove one composite-key term, remove an inner join condition, drop/change a categorical filter, and flip EXISTS/NOT EXISTS. These must fail coverage. Tests also reject empty/mutated correlation lists and verify that an uncorrelated model replacement is withheld at the service boundary.

Final verification: **160 backend tests passed** (45 added tests over the 115-test baseline), with one existing Starlette/httpx deprecation warning; **three frontend tests passed**; TypeScript and lint passed. Original reference suite: **58/58**. Existing cross-schema suite: **32/32**. No frontend behavior or unrelated features were added.

## Evaluation integrity and reserved final archive

Only the development manifests/reports and explicitly constructed development test fixtures were used. Historical 22/90 and 48/90 baseline artifacts remain unchanged; all 108 cases remain development-exposed. No new final archive was generated, and no reserved archive, answer file or receipt was opened or executed for this increment. Final-set construction logic was not inspected or used for tuning; normal source fingerprinting hashes repository script bytes without exposing their contents or final answers.

The old reservation's production-source hash is historical now that code has changed. Its final questions remain uninspected. Before any future final test, record a new code/prompt freeze and explicit release under the existing policy; do not claim a current final score or replace unseen final data to fit development results.

## Reproduction

```powershell
.\.venv\Scripts\python.exe scripts/run_independent_evaluation.py --systems deterministic --output logs/my-existence-run.json
.\.venv\Scripts\python.exe scripts/compare_development_reports.py --before logs/compositional-v1-development-verified.json --after logs/my-existence-run.json --example-ids education-05 education-21 collaboration-22 --output logs/my-existence-comparison.json
.\.venv\Scripts\python.exe scripts/summarize_remaining_operations.py --after logs/my-existence-run.json --output logs/my-existence-operations.json
.\.venv\Scripts\python.exe scripts/run_benchmark.py --output logs/my-existence-canonical.json
.\.venv\Scripts\python.exe scripts/evaluate_dataset_pack.py --output logs/my-existence-old32.json
```

All report names must be new. Actual artifacts: `logs/existence-v1-development-final.json`, `logs/existence-v1-comparison-final.json`, `logs/existence-v1-operations-final.json`, `logs/existence-v1-canonical58.json`, and `logs/existence-v1-old32.json`.

## Next recommended increment

Extend **typed timestamp predicates inside EXISTS**, not free-text SQL: explicit inner date windows and validated outer/inner timestamp comparisons. Three development cases need these operations (`education-26`, `education-30`, `logistics-26`). Validate each timestamp role/representation and inclusive/exclusive bounds, retain the same outer grain, and add missing/mixed-date and boundary counterexamples before enabling execution. Three is potential coverage, not a promised score gain.

The larger remaining families—ordered funnels (7), distinct activity grounding (6), and normalized event catalogs (5)—need additional identity/grain or ordered-stage contracts. They should not be enabled by loosening lexical confidence, ignoring unmatched words or treating every event as membership.
