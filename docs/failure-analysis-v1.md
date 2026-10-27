# Veyra: failure analysis and proposed generalization plan

## Executive finding

The main problem is not that users need better prompts. The offline planner can recognize a table and emit safe SQL while failing to represent the rest of a clearly stated question. Safety validation checks whether a query is allowed and uses existing identifiers; it does not check whether that query answers the question.

Reviewed all 108 questions, generated SQL/responses, references and expected results from the full offline run. Reverified all reference SQL against Python answers and reproduced the same baseline. No query-generation, schema-discovery, profiling, metric calculation or LLM-prompt changes were made. The only evaluator behavior change is exposure labeling through a separate registry; this cannot change scores.

Scope: the full deterministic/semantic pipeline, not all 108 Ollama responses. The previous model comparison is only a 15-case pilot, and no hybrid response in that pilot used model generation. It is not evidence that a larger model or different prompt would solve the failures.

## Baseline, unchanged

| Measure | Result |
|---|---:|
| Exact-result accuracy on answerable queries | 22/90 = 24.4% |
| Overall labeled-outcome correctness | 37/108 = 34.3% |
| Answerable queries executed | 65/90 = 72.2% |
| Wrong executed answers to answerable queries | 43 |
| Unnecessary clarifications on answerable queries | 17 |
| Exceptions on answerable queries | 8 |
| Correct clarification labels | 9/12 |
| Ambiguous questions incorrectly answered with rows | 2/12 |
| Exception instead of clarification | 1/12 |
| Correct write-request refusals | 6/6 |

There are 68 failures among the 90 query targets and three among the 12 clarification targets: 71 total. All nine exceptions happen during join SQL construction, before SQL reaches SQLite execution. The evaluator's broad error counter does not mean SQLite executed nine bad statements.

## Failure classification

Primary categories partition all 71 failures. A question can involve multiple defects: secondary labels record overlap but must not be added to the primary counts. The primary label is the dominant observed mismatch, not proof that fixing it alone would make a case pass.

| Requested category | Primary failures | Cases involving category, including secondary labels |
|---|---:|---:|
| 1. Schema/column identification | 5 | 33 |
| 2. Joins/table relationships | 18 | 39 |
| 3. Filtering/aggregation | 18 | 44 |
| 4. Dates/time | 12 | 22 |
| 5. Business metric interpretation | 7 | 9 |
| 6. Missing clarification on ambiguity | 2 | 3 |
| 7. SQL generation/execution errors | 9 | 9 |
| 8. Evaluation/reference-answer issues | 0 | 1 |

Category 8's zero primary failures does **not** mean the evaluation is flawless. One failed case raises a precision-contract concern; two reported passes are accidental matches; five correct clarification labels have weak follow-up content. These are recorded separately below and in the per-case audit.

### 1. Wrong entity or measure table

Examples: `education-19` asks for viewing minutes by learner region; the service selects learners as the measure table and asks which learner field to sum. `collaboration-17` asks for audit-action counts by catalog label; SQL counts catalog entries instead of audit occurrences. `collaboration-29` cannot connect “actors” to audit_log.actor_id.

Observed implementation: lexical table scoring, whole-column-token matching and a single primary table. Entity, fact grain, measure source and grouping source are not separate plan concepts. Cross-table wording can cause the grouping table to replace the fact table.

### 2. Relationships are not represented adequately

Examples: `education-20`, “learners without an enrollment,” lists every learner; `logistics-25`, parcels with a shipping charge and a refund, counts all parcels; `collaboration-11` through `13` omit the action_catalog join and return the entire audit log. Other explicit anti-join queries produce a lexical table-tie clarification even though their relationship is unambiguous.

Observed implementation: join planning primarily connects the chosen primary table to one selected dimension. It does not model anti-joins, semi-joins, relationship predicates, grouping over bridge-table membership, fact-versus-dimension grain or multiple role aliases. The catalog already discovers foreign-key edges: simply adding more graph traversal is not sufficient.

### 3. Conditions and aggregation are silently dropped

Examples: `education-10` omits `score IS NULL`; `education-29` omits `score >= 50`; `logistics-30` omits `weight_grams > 400`; `collaboration-09` averages all invoices instead of paid invoices. “Each region” does not produce grouping, and top-three requests do not produce the requested projection/ranking/limit. “Net charged cents” becomes COUNT rather than SUM.

Observed implementation: a small aggregate keyword list, dimensions recognized through “by,” sampled-value equality filters and a raw-row fallback. No general null/numeric/negation/HAVING/ranking representation exists. A filter's absence does not prevent execution.

Value-profiling evidence: education and logistics profiles are empty; collaboration profiles only organization.plan. Fields named state, stage and label do not satisfy the categorical allowlist. Therefore explicit values such as paid, delivered and sign_in are not available to the current sampled-value matcher. This is a coverage gap, not justification for indiscriminately profiling sensitive columns.

### 4. Temporal meaning is incomplete

Examples: `education-14` rejects joined_on as unrecognizable; `logistics-14` rejects shipped_on; `collaboration-14` rejects issued_on. Daily totals become lifetime totals. Date-order relationship conditions are absent from `education-26` and `logistics-26`.

Observed implementation: `_date_column` recognizes timestamp, *_at, date and time, but not these *_on fields. `_time_window` delegates to a month matcher that parses “on or after March 10 and before March 20, 2026” as the entire month of March. That parser behavior was reproduced directly; in the scored case, date-column rejection occurs first, so the whole-month error is a **latent additional defect**, not the observed cause of that case's returned clarification.

Naming aliases alone will not solve inclusive/exclusive bounds, grouping grain, relative clocks or comparisons between timestamps from related tables.

### 5. Explicitly defined funnels are not compiled

Seven failures: education 27–28, logistics 27–28, collaboration 26–28. The questions explicitly specify order, same-day handling, entity scope and, where relevant, denominator. The responses count an entity table or return rows rather than compute the ordered relationship/ratio.

Observed: the semantic plan has no ordered-stage or numerator/denominator representation. These are missing analytical operations, not necessarily missing user definitions. A semantic layer is useful for future ambiguous activation/retention requests, but alone cannot implement an already defined funnel.

### 6. Clarification is inconsistent

`education-33`, “best learners,” and `logistics-34`, “best depot,” return raw records without asking what best means. `logistics-31`, counts by zone, should ask origin versus destination but crashes first. The latter is primary category 7 and secondary category 6, avoiding double counting.

Conversely, 17 answerable questions receive unnecessary clarifications. A low lexical confidence score is not equivalent to ambiguity in the business question. The service needs to distinguish missing business definitions, unsupported operations, missing data and unresolved lexical grounding.

### 7. One confirmed metadata defect explains all nine exceptions

Examples: enrollment counts by course subject, parcel counts by destination zone and paid invoice cents by plan.

These fixture declarations use valid SQLite shorthand such as `course_id REFERENCES courses`. SQLite reports an omitted referenced-column name as null. `discover_schema()` stores it as target_column=None; `_join_sql()` calls `_qualified()` and `_quote()`, which calls `.replace()` on that value. A traceback reproduced this exact chain.

The relation is not absent and the database is not corrupt. The adapter fails to resolve implicit referenced primary keys. Resolving it should remove this exception class, but may expose other failures: first-edge selection can still confuse origin/destination roles, and aggregates/grain may still be wrong. No resulting accuracy gain has been measured.

### 8. Evaluation weaknesses, distinct from product failures

- **Two accidental passes, confirmed with counterexamples.** `education-05` counts all learners instead of distinct enrolled learners; `collaboration-05` counts all people instead of members. Every existing person participates, so the answers coincide. Adding one nonparticipant to an in-memory copy changes the generated results from 24 to 25 and 18 to 19 respectively, while references remain 24 and 18. Frozen databases are byte-unchanged. Do not count these counterexamples as newly scored official cases or silently revise the baseline.
- **Unrequested rounding.** `education-09` produces ROUND(AVG(score),2), while the expected unrounded value is 48.15384615384615. It is a real exact-result mismatch under the current tolerance, but not a wrong AVG/null exclusion formula. Make display rounding separate from computation; do not loosen tolerance after seeing results to improve the score.
- **Clarification wording is not scored.** Five of the nine category-correct clarifications ask which table rather than the actual missing definition/field. Outcome-label accuracy overstates helpfulness. Add a separate rubric rather than rewriting the historic result.
- **No confirmed reference-SQL/Python disagreement.** All reference executions still agree with the independent Python answers. This does not prove every natural-language interpretation is unique; the author is not an independent human reviewer.

## Three recommended changes, in priority order

### 1. A compositional query plan with coverage checks

Extend the existing typed plan incrementally: entity/fact grain, measure and function, distinct key, predicates and null policy, grouping list, time window/grain, relationship requirements, ordering/limit and ordered-stage definitions. Separate parsing, grounding, plan validation and SQL compilation. Preserve canonical working paths during migration.

Before execution, verify that material requested operations are represented. Unsupported explicit operations should return a clear unsupported-operation response or use a deliberately configured model path; genuinely missing meanings should ask focused clarification. Never replace “at least 50” with an unfiltered lookup.

Why first: filtering/aggregation is involved in 44 failures, temporal logic in 22, and seven explicit metrics need compositional operations. These overlap and are not a predicted improvement count. This is the broadest structural gap. Begin with predicates, distinctness, grouping and precise time windows; add ranking/anti-joins/funnels only behind focused development tests.

### 2. Normalize and validate relationship metadata and grain

Resolve omitted referenced columns against the actual ordered primary key; retain constraint identity and column order for composite keys. Validate endpoints before SQL construction. Represent role-specific edges/aliases, preserve measure grain and avoid fanout with explicit semi/anti-joins or preaggregation. Ask for a role only when the question really leaves it unspecified.

Why second: 18 primary relationship failures and nine primary exceptions. The None target defect is directly reproduced. Composite handling, multi-edge ambiguity and cardinality are additional observed design limits; their independent accuracy impact remains unmeasured. Never infer a trustworthy join solely from similar names.

### 3. An approved semantic layer for grounding and business definitions

Use versioned mappings for entity keys, event catalogs, approved categorical fields, timestamp roles/formats/timezone, sessions, amount units/currency/refunds, and metric contracts. Bind facts separately from dimensions. Keep approval explicit, reject stale schemas and unresolved definitions, and return mapping version/definitions with results. Only profile explicitly safe categories within current bounds.

Why third: wrong fact/entity binding, empty categorical profiles, date-name dependence and undefined best/metric terms demonstrate a need for controlled semantics. Mapping cannot replace query planning, resolve every relationship, or turn existing syntax validation into semantic validation. Test actual metric integration later with development-only schemas, not the final set.

No LLM fine-tuning is recommended as the first response: these are confirmed deterministic-pipeline defects and no full LLM baseline establishes a training bottleneck. No numerical gain is promised for any proposal.

## Integrity and measurement plan

1. All 108 v1 cases are now **development-exposed**, including passing cases. The 58 and 32 suites were already development cases. No split of those reviewed cases can become genuinely untouched.
2. Preserve original manifest/database hashes, labels, answers and score reports. `docs/evaluation-registry.json` records role/exposure keyed by the immutable manifest hash. New evaluator reports consult it; old report labels remain historical, not current claims.
3. No untouched final set exists yet. Have a separate author/custodian prepare fresh schemas/questions with verified references, keep labels and per-case feedback away from planner/prompt development, and preregister hashes, conditions and acceptance criteria. A newly generated seed of these same templates is not strong structural holdout evidence. Do not score it until implementation and prompts are frozen.
4. Develop the three changes on v1 plus separate operation-focused and counterexample fixtures. Re-run the exact same original 90-query/108-outcome baseline after each change; show per-case transitions, categories, unnecessary clarification, errors and old-suite regressions. Added counterexamples get their own versioned report, not a retroactively changed denominator.
5. Complete full model-only/hybrid comparisons under fixed settings before comparing systems. Treat pilot results as partial. Report actual model use and model identity. Coverage checks may lower execution errors without improving exact answers; measure both separately.
6. Use final evaluation once ready. If final failures are used for tuning, retire its untouched status and commission a replacement before another final claim.

## Reproduce the audit

```powershell
.\.venv\Scripts\python.exe scripts/analyze_independent_failures.py --output logs/my-failure-audit.json --markdown-output docs/my-case-audit.md
.\.venv\Scripts\python.exe scripts/run_independent_evaluation.py --systems deterministic --output logs/my-development-baseline.json
.\.venv\Scripts\python.exe scripts/run_benchmark.py --output logs/my-original-regression.json
```

Choose new output filenames; reports are not overwritten. The analysis script validates all 108 IDs, exactly covers all 71 failed cases, records baseline/manifest hashes and verifies references. It does not alter the production planner or source databases. See [all 108 case annotations](failure-analysis-v1-cases.md) and `logs/independent-v1-failure-analysis-reviewed.json` for the evidence ledger. Two in-memory counterexamples are diagnostics only.

## Verification and next decision

Before changes: all 70 existing backend tests and three frontend tests passed; the original benchmark remains 58/58. After the audit/exposure-reporting update: 72 backend tests pass (two additional governance tests), with one existing Starlette/httpx deprecation warning. No frontend implementation changed. The full 108-case rerun preserves every case outcome and generated SQL, and the original manifest hash is unchanged. Current reports explicitly label the suite development-exposed and ineligible for final evaluation. SQL generation remains unchanged and no accuracy improvement is claimed.

Verification artifacts: `logs/independent-v1-failure-audit-rerun.json`, `logs/independent-v1-development-labeled-baseline.json`, `logs/failure-audit-original-regression.json` and `logs/independent-v1-failure-analysis-reviewed.json`.

The proposed next implementation is the compositional-plan/coverage work, paired with the narrow implicit-FK metadata repair. Broad semantic-layer UI work comes after its validation contracts are agreed. This report stops at analysis, planning and evaluation-governance changes, as requested.
