# Reliability improvement plan

## Baseline and preservation

Starting point: commit `cbac2f9` plus existing uncommitted cross-schema diagnostics/example retrieval work. Preserve those changes. No replacement of the planner, analytical modules, database registry or UI is planned. Baseline backend: 62 tests pass (one Starlette/httpx deprecation warning). Frontend baseline: three tests pass. First-increment verification: 70 backend tests pass and the original 58-case regression remains 58/58. See `independent-evaluation-results.md` for completed versus pending work.

## Prioritized increments

1. **Independent evaluation infrastructure (first).** Audit the existing suites, freeze three structurally different schemas and at least 100 labeled questions, verify SQL against separately calculated Python answers, and persist fingerprints. Compare offline deterministic/semantic generation, schema-aware Ollama-only generation, and the existing hybrid service. Use identical safety/execution limits; no reference answers or few-shot examples in prompts. Distinguish wrong answers, unnecessary clarifications, execution failures, invalid-request refusals and unavailable systems. Record complexity denominators. Do not tune the planner against the frozen set.
2. **Approved semantic contracts.** Design versioned per-database mappings for users, events, sessions, revenue, activation, retention and conversion. Validate identifiers, relationships, uniqueness, timestamps, units and required definitions. Save drafts separately from approved versions. UI must expose assumptions and require explicit approval; ambiguous definitions stay unset. Adapt existing metric services through validated canonical projections where compatible, without replacing their mathematics. Reproduce results with mapping version and database identity. Test stale schema rejection and workflow parity before enabling mappings.
3. **Experimentation verification.** Independently check pooled proportion tests, unpooled difference intervals, allocation diagnostics, Welch guardrails and prospective planning. Add unequal allocation, zero outcomes, sparse/degenerate samples, duplicate assignments and incomplete observation fixtures. Document event completeness, fixed-horizon and randomization assumptions. No advanced inference until independently justified.
4. **Local product readiness.** Add opt-in local aggregate instrumentation with no questions, SQL, values, filenames or personal identifiers. Define retention/deletion and avoid network telemetry. Add upload compatibility review, unresolved-definition guidance, and metric/statistics explanations. Keep local-only operation; do not enable public users or expose data. Maintain a public-deployment blocker checklist.

## Evaluation integrity gates

- Freeze fixtures before scoring; tests of the harness use separate toy fixtures.
- Reference SQL must agree with an independently calculated oracle before any score is produced.
- Schema metadata/sample values are permitted inputs; labels, oracle rows, reference SQL and training examples are not.
- Record suite/database/code hashes, settings, model identity, skips, run order and per-case actual source.
- Newly authored cases are separate from prior prompt/training exports, but this is internal author-separated evaluation, not an external blind assessment.
- If final cases are used to debug generation, mark the suite development-exposed and create a new final set before claiming generalization.
- Do not substitute a missing model with offline output in a model-only run. Incomplete model runs are partial, never full scores.

## Delivery gates

Run existing tests before/after each increment, add focused tests, preserve existing data and configuration, and save reproducible reports. Report implemented versus remaining work explicitly. Resume claims must identify synthetic fixtures and development exposure; no user adoption, production deployment or model-training claims without evidence.
