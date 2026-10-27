# Synthetic testing before further planner improvements

## What was added

No planner or application behavior was changed. This increment adds a reproducible development-only generator, oracle-integrity tests, paired synthetic snapshots, and a failure evidence exporter.

- **Rentals:** renters, equipment, bookings, and inspections; inspector/reviewer are different foreign-key roles referencing the same entity table.
- **Support:** requesters, queues, tickets, responses, tags and assignments; tag namespace/code is a composite key. The same code has different meanings in different namespaces, so omitting a join key produces false matches.
- **Billing:** subscribers, plans, charges, normalized event kinds and usage events. Repeated opens, export-before-open, inactive subscribers and unused catalog entries distinguish event counts, observed identities and ordered conversion.

There are **90 question formulations**, run on **two seeded variants** (11 and 29): six SQLite databases and **180 evaluated case executions**. Each variant has 78 answerable queries, six clarification labels and six write refusals. Each schema has 24 shared operation controls plus six domain-specific questions. The paired variants repeat questions; they are not 180 independent linguistic questions. The support domain overlaps a prior diagnostic domain, but its composite tag structure and new questions are distinct; this is broader development testing, not a claim of wholly unseen business domains.

Data includes duplicate entity activity, NULL measures/relationships/timestamps, zero values, ties, registered entities without facts, unused dimensions, inclusive/exclusive boundaries, March/April boundaries and timezone offsets crossing UTC midnight. Seeds vary fact counts, entity assignments and measures. These are small fixtures, not realistic load/performance benchmarks. Missing foreign keys, epoch/malformed dates, adversarial text, large-scale profiling and multiple dialects remain coverage gaps.

## Reference validation and evaluation integrity

Expected rows are calculated using Python collections over source records, separately from reference SQL execution. Before scoring, the existing harness validates every reference with SQLGlot, executes it read-only, checks SQL/Python result agreement, and checks database hashes. Generator tests verify reproducibility, refusal to overwrite snapshots, changed expected results across seeds, nonempty positive/negative relationship examples, composite-key counterexamples, UTC boundaries, and detection of corrupted references.

This is computational cross-validation by the same development author, **not independent human verification**. Shared misunderstanding can still affect both oracles. All cases are development-exposed immediately, registered as ineligible for final evaluation. No reserved final archive, receipt, answer file or construction logic was opened or executed. Standard source fingerprinting hashes script bytes without exposing final answers. Production file fingerprints match the preceding 64/90 implementation snapshot.

Only the existing deterministic pipeline was measured, with the model disabled, examples disabled, a 5,000-row cap and eight-second execution limit. No Ollama-only or hybrid accuracy claim is made.

## Results: each seeded variant

Both variants produce the same outcome/correctness classification on every question, despite changed data and expected values. This is limited paired-value stability, not proof of robustness.

| Metric | Seed 11 | Seed 29 |
|---|---:|---:|
| Exact query results | 42/78 (53.8%) | 42/78 (53.8%) |
| Executed answerable queries | 47/78 (60.3%) | 47/78 (60.3%) |
| Correct overall outcomes | 54/90 (60.0%) | 54/90 (60.0%) |
| Unnecessary clarifications | 31 | 31 |
| Wrong executed answers | 5 | 5 |
| Correct clarification labels | 6/6 | 6/6 |
| Correct write refusals | 6/6 | 6/6 |
| Exceptions / unsafe attempts | 0 / 0 | 0 / 0 |

Across both variants: 84/156 exact query results; 108/180 correct overall outcomes; 62 unnecessary clarifications; ten wrong executions. Those aggregate observations repeat the same five wrong question formulations, not ten independent bugs. Among executed answerable queries, 42/47 (89.4%) have exact results.

Per schema, identical across variants:

| Schema | Exact query results | Executed | Overall correct | Wrong executions | Unnecessary clarifications |
|---|---:|---:|---:|---:|---:|
| Rentals | 13/26 | 16/26 | 17/30 | 3 | 10 |
| Support | 15/26 | 16/26 | 19/30 | 1 | 10 |
| Billing | 14/26 | 15/26 | 18/30 | 1 | 11 |

By author-assigned query complexity: simple 28/37 exact, 31 executed, three wrong, six withheld; medium 13/32 exact, 15 executed, two wrong, 17 withheld; complex 1/9 exact, one executed, none wrong, eight withheld. Complexity labels are descriptive, not standardized benchmarks.

## Confirmed incorrect answers

These are observed semantic errors, not merely unsupported questions:

1. `rentals-19`, `support-19`, `billing-19`: “where fee/effort/amount is zero” compiles to `column = 'zero'` rather than numeric zero. The generated SQL returns 0 while each Python/reference result is 7. Both variants show this mismatch. The observed defect is literal interpretation; the internal reason for accepting that interpretation has not been traced in this testing increment.
2. `rentals-25`, `rentals-26`: “Count distinct inspectors/reviewers from inspections” compiles to `COUNT(DISTINCT inspection_id)`. Both return 5 instead of the correct 3 distinct inspector/reviewer IDs. The observed defect is identity-role substitution, not ambiguity in the requested role. The exact routing/fallback cause remains to be audited.

The existing AST coverage checker can validate SQL against an incorrectly grounded plan. These examples demonstrate why SQL validity and plan/SQL agreement alone do not establish natural-language correctness. The previous 108-case suite's zero-wrong-answer observation must not be generalized to unfamiliar schemas.

All wrong SQL, reference SQL, expected rows and actual rows are exported in `logs/synthetic-stress-v1-diagnostics.json`. That file also includes every withheld request and the actual clarification message; none of these failures were fixed or removed to improve the score.

## Withheld operations: observations versus hypotheses

31 answerable questions per variant are withheld. Primary manual capability grouping (mutually exclusive here):

| Requested capability | Cases |
|---|---:|
| Explicit distinct identity / assignment identity | 4 |
| NULL foreign-key filtering | 3 |
| Plain “at least one” existence wording | 3 |
| Daily counts with explicit UTC/NULL policy | 3 |
| Joined grouping with explicit missing-relationship policy | 3 |
| Ranking with tie/NULL rules | 3 |
| Grouped count threshold / HAVING | 3 |
| Parallel-role comparison | 1 |
| Numeric filtered existence | 1 |
| Explicit temporal existence wording | 1 |
| Composite-key catalog grounding | 2 |
| Normalized event catalog grounding | 2 |
| Ordered funnels / denominator | 2 |

Observed messages include unsupported compound relationship operations, unresolved timestamp/UTC terms, unresolved missing-value conditions and unmatched relationship intent. Some requests explicitly name a field but are still treated as related-entity requests. A plausible hypothesis is that lexical routing/term coverage blocks several otherwise representable operations; a planner trace audit is needed before assigning internal causes. Other cases genuinely require unsupported operators such as HAVING or ordered stages. Do not assume all 31 would be fixed by one feature or by relaxing coverage checks.

## Existing-suite verification

The original 108-case deterministic evaluation remains **64/90 exact, 82/108 overall, 26 unnecessary clarifications and zero wrong executions**, with zero previous-pass regressions. Canonical benchmark remains **58/58** and existing cross-schema diagnostics **32/32**. These are unchanged-suite checks, not improvements caused by new tests. **220 backend tests passed**, including six new fixture-integrity tests over the 214-test starting suite; **three frontend tests**, TypeScript and ESLint also passed. One existing Starlette/httpx deprecation warning remains. `git diff --check` passed.

## Recommended next work, not implemented

First investigate and fix the two confirmed wrong-answer families: typed numeric literal grounding and explicit requested-identity preservation. Add narrowly scoped negative/counterexample tests and require ambiguous bindings to clarify. Then trace the representable-but-withheld requests before choosing new architectural features. Catalog grounding and ordered funnels remain useful, but should not take priority over silently incorrect answers.

## Reproduction and files

```powershell
.\.venv\Scripts\python.exe scripts/build_synthetic_stress_suite.py --output datasets/evaluation/my-stress-seed11 --seed 11
.\.venv\Scripts\python.exe scripts/run_independent_evaluation.py --pack datasets/evaluation/my-stress-seed11 --verify-only
.\.venv\Scripts\python.exe scripts/run_independent_evaluation.py --pack datasets/evaluation/my-stress-seed11 --systems deterministic --output logs/my-stress-seed11.json
# Repeat with a new directory/report and seed 29.
.\.venv\Scripts\python.exe scripts/summarize_synthetic_stress.py --packs datasets/evaluation/synthetic-stress-v1-seed11 datasets/evaluation/synthetic-stress-v1-seed29 --reports logs/synthetic-stress-v1-seed11-deterministic.json logs/synthetic-stress-v1-seed29-deterministic.json --output logs/my-stress-diagnostics.json
```

Choose new output directories/filenames; snapshots are never overwritten. Regenerated manifests have the same fingerprints for the same seed. A new seed is unregistered until explicitly recorded as development metadata; it is not implicitly held-out.

Source: `scripts/build_synthetic_stress_suite.py`, `scripts/summarize_synthetic_stress.py`, `backend/tests/test_synthetic_stress_suite.py`, and development entries in `docs/evaluation-registry.json`. Databases/manifests under `datasets/evaluation/` and reports under `logs/` are intentionally ignored by Git; commit-worthy generator/test code reproduces them.

Actual artifacts: `logs/synthetic-stress-v1-seed11-deterministic.json`, `logs/synthetic-stress-v1-seed29-deterministic.json`, `logs/synthetic-stress-v1-diagnostics.json`, `logs/synthetic-testing-original108-verified.json`, `logs/synthetic-testing-canonical58.json`, and `logs/synthetic-testing-crossschema32.json`.
