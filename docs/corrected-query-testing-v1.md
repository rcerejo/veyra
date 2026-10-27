# Corrected-query stress testing and bounded binding fixes

This increment first expanded diagnostics without changing production behavior, then fixed two confirmed wrong-answer paths with the user's explicit approval. All cases are development-exposed. The reserved final archive, answers and construction logic were not opened or executed.

## Data and methodology

The matrix contains four renamed role/type families (quality, dispatch, content, commerce), each with two role foreign keys, duplicate participants, inactive parents, NULL identities, signed numeric amounts and contrasting text categories. Seeds 23 and 59 produce eight database contents. These families share a graph shape; they are not four independently diverse structures.

The main matrix has 168 formulations, repeated on two seeds (336 executions). Supplemental contrastive probes add 32 formulations repeated on the same database contents (64 executions). Thus the combined denominator is **400 executions, 200 question formulations, eight database contents**, not 400 independent questions. Source-tuple Python oracles are checked against reference SQL before evaluation. There was no independent human reference review. Interpretations such as a role FK meaning the person performed an activity are fixture assumptions, not universal business definitions.

Generation scripts refuse to overwrite existing packs. The four manifests are registered as development-only in `evaluation-registry.json`. No training, prompt examples or Ollama-only/hybrid measurements were added.

## Observed failures and implementation

1. **Field/value binding: 24 wrong executions.** For example, `Count reviews with fee of zero` previously produced a filter on `status = 'zero'`, because category sample matching recognized `zero` while the numeric field phrase was not represented. Coverage validated that incorrectly grounded plan. The planner now binds bounded numeric `field of value` and `with zero field` phrases before category sampling, and masks those spans from unrelated categorical matching. It uses existing typed equality conversion, structured filters, compilation and SQL coverage validation.
2. **Text punctuation: 16 wrong executions.** `Count reviews where status is PASS.` previously filtered on `'PASS.'`, yielding zero rather than the nonempty reference result. Terminal prose punctuation is removed from the equality parsing surface. Punctuation inside quotes remains literal: `status is "zero."` must not become `status = 'zero'`.

An intermediate implementation treated every `field of word` phrase as equality and regressed `Total minutes of lesson viewing`. Case-level comparison exposed it. The final implementation restricts the new `of` form to numeric literals/number words, with a regression test for this aggregate. Intermediate reports remain preserved, not presented as final results.

Illustrative structured plan changes:

| Request | Before filter | After filter |
| --- | --- | --- |
| Count reviews with fee of zero | status / eq / text `zero` | fee / eq / numeric `0` |
| Count reviews where status is PASS. | status / eq / text `PASS.` | status / eq / text `PASS` |
| Count reviews where status is "PASS." | status / eq / text `PASS.` | unchanged literal |

No SQLGlot validation, mutation detection, read-only execution, date logic, distinct identity logic or unsupported Boolean guard was removed. Conflicting equalities and unresolved numeric descriptions still require clarification.

## Same-denominator development results

| Metric | Before | After |
| --- | ---: | ---: |
| Exact query results | 232/352 (65.9%) | 280/352 (79.5%) |
| Query execution coverage | 272/352 (77.3%) | 280/352 (79.5%) |
| Wrong executed answers | 40 | 0 |
| Unnecessary clarifications | 80 | 72 |
| Overall correct outcomes | 280/400 (70.0%) | 328/400 (82.0%) |
| Genuine clarification outcomes | 32/32 | 32/32 |
| Write-request refusals | 16/16 | 16/16 |
| Errors / unsafe attempts | 0 / 0 | 0 / 0 |

The original corrected controls remain 200/200. Nearby wording queries improve from 16/88 to 24/88; contrastive probes improve from 16/64 to 56/64. These are development fixes, not held-out generalization. Zero wrong answers here does not mean the whole platform has zero wrong-answer paths.

The fingerprint-checked comparison records **48 previous failures fixed (40 wrong executions, eight unnecessary clarifications), zero previous passes regressed**. Both data seeds have identical correctness/outcome classifications. Final evidence is in `logs/corrected-combined-binding-final-audit.json` and `logs/corrected-binding-final-comparison.json`; detailed plans, SQL, references and actual rows are in `logs/corrected-matrix-binding-final-audit.json` and `logs/literal-probes-binding-final-audit.json`.

Remaining withheld forms include equality symbols, `have a fee of zero`, `is equal to zero`, participation wording, distinct row lists, OR/NOT, repeated equalities and sentence-final exclamation marks caught by the unsupported predicate guard. The next increment should use typed predicate spans and operator-aware coverage rather than globally relaxing these guards. Separately, the existing context diagnostic still exposes a UTC-boundary wrong answer and unsupported ordered-funnel behavior.

## Tests and reproduction

Tests cover oracle integrity, reproducibility, empty/all-NULL facts, duplicate-event versus distinct-person invariants, inactive registrations, renamed fields, quoted punctuation, contradictory/unsupported bindings and SQL filter mutations. Nine joined-snapshot variants vary seeds and source aliases, check join grain, reject mutated relationship keys, preserve source bytes and ensure old snapshots remain stable after new source data. Passing unit tests do not imply all diagnostic questions are supported; the evaluation explicitly counts withheld answerable cases as failures.

Verification: **340 backend tests pass** (`logs/binding-final-backend.xml`, one existing Starlette/httpx deprecation warning); **15 frontend tests pass**. TypeScript and ESLint checks also pass. Baseline backend tests were 307 before this testing increment. Three initially failing new tests incorrectly expected an exception instead of the planner's returned clarification; the assertions were corrected without relaxing production behavior. A reference-verification timeout under concurrent load was retried without changing timeout/security limits; incomplete runs are not measurements.

Existing deterministic outcomes are unchanged after the final fix: original development 64/90 exact and 82/108 overall; canonical 58/58; cross-schema 32/32; stress seeds 11/29 each 50/78 exact and 62/90 overall; context 12/15 exact and 23/26 overall (one pre-existing wrong UTC result). The intermediate aggregate-description regression was removed and the original 108-case comparison has zero previous-pass regressions. Production fingerprints show only `backend/app/query_engine/compositional.py` changed relative to this increment's baseline; existing working-tree changes were preserved.

From the repository root, generate new development packs only into new directories:

```powershell
& .\.venv\Scripts\python.exe scripts/build_corrected_query_matrix.py --help
& .\.venv\Scripts\python.exe scripts/build_literal_collision_probes.py --help
& .\.venv\Scripts\python.exe scripts/run_independent_evaluation.py --pack datasets/evaluation/corrected-query-matrix-v1-seed23 --systems deterministic --output logs/NEW-matrix-seed23.json
```

Repeat evaluation for both seeds of both suites. Reports refuse existing output filenames. Audit with `report_corrected_query_matrix.py --packs ... --reports ... --output ...`, then combine the two audits using `--combine-audits`. Compare before/after audits with `compare_corrected_query_audits.py`; this verifies identical seed/ID denominators, manifest hashes, questions, references and expected rows before counting fixed cases or regressions.

Baseline evidence: `logs/corrected-more-combined-audit.json`, `logs/corrected-query-matrix-v1-audit-verified.json`, `logs/literal-collision-probes-v1-audit-verified.json`. Final raw evaluations use the `binding-final.json` suffix. Original baselines and fingerprints remain unchanged. No accuracy, deployment or adoption claims beyond these measured development runs are warranted.
