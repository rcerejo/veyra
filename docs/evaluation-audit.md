# Audit of existing NL-to-SQL evaluation

## 58-query demo benchmark

Source: `backend/app/metrics/evaluation.py`, exposed through the Evaluation page and `scripts/run_benchmark.py`.

Measures result-multiset agreement against hand-written SQL on the active database, plus executed-query counts, correction counts, wall latency and Python traced peak allocations. Aliases and row order are ignored. It includes simple counts, categorical groups, date filters, canonical metric queries, joins and four read-only/clarification cases. There are 32 month/event permutations across four months; these are useful regressions, not 32 independent reasoning patterns.

The reference SQL is separately written from generation, but both target known canonical tables. Planner templates and tests coexist in the repository and the benchmark has been used repeatedly during development. Treat all 58 as development-exposed. High scores demonstrate compatibility with those contracts, not arbitrary-schema generalization.

Limitations: expected rows are computed by SQL at run time, not an independent non-SQL oracle; null/empty and low-diversity data can make wrong queries accidentally agree; all non-query responses satisfy either rejection or clarification labels; no complexity strata; exact float equality; row ordering ignored even for ranking questions; a row cap can hide omitted results because reference truncation is not checked. Running on an incompatible active database is not a valid portability score. Python tracemalloc is not process RSS. The direct LLM baseline receives no schema while the schema-aware baseline does, so those are different input conditions. Missing model runs are skipped honestly.

## 32-case cross-schema diagnostics

Sources: `scripts/generate_test_datasets.py`, `scripts/evaluate_dataset_pack.py`, `scripts/prepare_sql_learning.py`.

Five families: commerce, subscriptions, support, messy records and renamed canonical demo. Compares complete result multisets with duplicate preservation and rounded floats. Checks references against independently prepared answers before scoring. Includes clarification labels. Renaming tests lexical dependence while retaining the original relational shape; it is not a structurally new data model.

The observed 23/32 to 32/32 change followed fixes made from these cases. All 32 are development-exposed. Commerce/support supply the 33 paraphrased training rows (11 distinct queries) and 11 retrieval examples. The other families are excluded from that export, but were inspected during development: `heldout.jsonl` is held out of training examples, not a blind final test.

Limitations: small fixtures and few query structures; paraphrases are correlated; no isolated model-only system; model-preferred execution retains semantic clarification gates and permits offline fallback; incomplete model identity; no complexity metrics; alias/order-insensitive result comparison. All 32 passing is not evidence of fine-tuning or universal dataset support.

## Contamination paths and controls

1. Canonical planner rules match benchmark wording. Keep their score as regression evidence.
2. Diagnostics used to debug the planner. Do not relabel them held-out.
3. Retrieval examples contain benchmark-family reference SQL. Disable examples for independent runs and never export final cases into learning data.
4. Repeated templates, copied schemas, one data seed and empty results inflate apparent diversity. Use structurally different fixtures and explicit nonempty/boundary cases; report family/complexity counts.
5. Global active-database selection and environment settings can change inputs. Explicitly bind each adapter and freeze evaluation configuration.
6. Model-only fallback can misattribute offline correctness to an LLM. Use strict modes and report actual sources, unavailable models and partial coverage.
7. Inspecting final failures then changing the planner contaminates the final set. Retain scores as an internal baseline and record exposure before any such debugging; create new untouched cases for final claims.

The next suite is independently authored relative to the existing cases and uses Python oracles, but shares an author with the system. It is not an externally blinded benchmark. Authoring SQL/labels is allowed; using score failures to tune generation is not allowed without changing its exposure designation.
