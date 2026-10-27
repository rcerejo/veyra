# Independent evaluation: first increment results

Date: October 26, 2026. This reports an internal synthetic baseline, not an accuracy improvement, external blind evaluation, fine-tuning result or production certification.

**Exposure update:** all 108 cases have now been inspected for failure analysis and are development-exposed. The historic scores below are preserved unchanged. See [failure analysis and proposed plan](failure-analysis-v1.md) and `evaluation-registry.json`. A later [compositional planner increment](compositional-planner-v1.md) reports development improvements and a separate reserved, unopened, unscored internal final archive; no final accuracy has been measured.

## Full offline baseline

Report: `logs/independent-v1-deterministic.json`.

| Measure | Observed result |
|---|---:|
| Correct labeled outcomes | 37/108 (34.3%) |
| Exact query results | 22/90 (24.4%) |
| Executed answerable queries | 65/90 (72.2%) |
| Correct clarifications | 9/12 (75.0% recall) |
| Clarification precision | 9/26 (34.6%) |
| Unnecessary clarifications on answerable questions | 17 |
| Explicit refusals of write requests | 6/6 |
| Exceptions / unsafe attempted queries | 9/108 (8.3%); zero unsafe attempts |

By query complexity:

| Complexity | Query cases | Exact results | Execution errors |
|---|---:|---:|---:|
| Simple | 38 | 22/38 | 0/38 |
| Medium | 33 | 0/33 | 5/33 |
| Complex | 19 | 0/19 | 3/19 |

The other error occurs in an undefined/clarification-target case. By schema, labeled-outcome correctness is education 12/36, logistics 11/36 and collaboration 14/36. These are case-weighted descriptive results, not population estimates.

Interpretation: the existing deterministic/semantic pipeline often executes a query but does not answer the requested question correctly on structurally unfamiliar schemas. Its development scores (58/58 and 32/32) substantially overstate the evidence for generalization if presented without qualification. These scores concern different datasets/question distributions and must not be described as a measured accuracy regression caused by this increment.

No production query-generation fixes were made from these new failures. Future debugging on the cases must change their exposure designation and requires a new final set for subsequent generalization claims.

## Three-system stratified pilot — partial only

Report: `logs/independent-v1-stratified-pilot.json`. The selected 15 questions contain one count, one join, one ordered funnel, one missing/ambiguous definition and one write request per schema. Nine require query answers, three require clarification and three require refusal. IDs and reproduction command are in `independent-evaluation.md` and the JSON report.

| System | Correct outcomes | Exact query results | Executed query targets | Unnecessary clarifications | Errors |
|---|---:|---:|---:|---:|---:|
| Offline deterministic/semantic | 9/15 | 3/9 | 6/9 | 0 | 3/15 |
| Ollama-only | 9/15 | 3/9 | 4/9 | 4 | 0/15 |
| Existing hybrid | 9/15 | 3/9 | 6/9 | 0 | 3/15 |

Each system correctly categorized all three clarification targets and three write requests. No unsafe SQL attempt occurred. Ollama-only ran the requested local `llama3.1:8b` (Q4_K_M), digest `46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e`. All 15 Ollama-only responses came from the model. No hybrid response used model generation on this selected subset: the existing deterministic/semantic routing and clarification gates handled or failed first. The hybrid pilot therefore does not establish the quality of its LLM fallback.

The pilot is not a full 108-case comparison and supplies no evidence that one system improves accuracy. The sample is deliberately stratified, small and not representative; latency is not compared because model warm-up was uncontrolled. Full Ollama-only and hybrid runs remain pending. Use the documented unrestricted command rather than extrapolating pilot percentages.

## Provenance and checks

- Final suite manifest SHA-256: `9bcbeaa7cbbc125d0f9e59f72a8f00d0070755a3a20e705246deee99b06cfaab`.
- Pilot source-file fingerprint: `f5f24d6ac4a8c81ba251c9a1d27c28a696743066bde39d694777c41a841fa924` (all file hashes in JSON).
- SQL references agreed with Python oracle answers on all 108 cases before generation scoring.
- Baseline backend tests: 62 passed. Final expanded suite: 70 passed (eight added harness tests), with one existing Starlette/httpx deprecation warning.
- Frontend baseline: three tests passed; no frontend implementation changed in this increment.
- Original benchmark after changes: 58/58, model baselines not run (`logs/independent-increment-original-regression.json`).

Methodology, limits and environment are documented in `independent-evaluation.md`. Evaluation artifacts are local synthetic data; no uploaded customer data was used or exposed.

## Implementation status

- Implemented: benchmark audit, prioritized plan, three new fixture generators, 108 questions/SQL references/Python answers, strict evaluation modes, result comparison and stratified metrics, provenance recording, toy harness tests, full offline baseline and model comparison pilot.
- Remaining in Phase 1: complete 108-case model-only/hybrid runs, independent human review and externally authored final validation. More seeds and robustness tests are useful extensions, not measured achievements.
- Phase 2: existing metric dependencies audited and a mapping/approval contract documented. No mapping persistence/API/UI or mapped analytics integration yet.
- Phase 3: no new statistical verification or inference changes in this increment; existing experimentation behavior is preserved.
- Phase 4: no new telemetry/onboarding UI. Existing deployment blockers remain: individual authentication/authorization, tenant isolation, workload isolation, protected storage/restore procedures and verified deployment operations. Public access is not enabled.

## Defensible resume wording

“Built a reproducible NL-to-SQL evaluation harness with 108 synthetic business questions across three structurally distinct SQLite schemas, independent Python answer checks, and complexity-stratified metrics.”

Do not claim improved held-out accuracy, trained model weights, production deployment or customer adoption from this increment. The demonstrated improvement is evaluation rigor and visibility into limitations, not query-generation accuracy.
