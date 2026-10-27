# Two synthetic sources, joined snapshot and completed context

## Deliverables

Current reviewed artifacts live in `datasets/test-packs/joined-context-v1-reviewed/`:

- `crm.db`: five accounts, eight people and ten membership relationships.
- `product.db`: 17 activity records and nine invoices/credits.
- `joined.db`: upload-ready combined snapshot of the two sources, with validated cross-source foreign keys.
- `dataset-context.md`: completed six-section context template, including vocabulary, row grain, identity roles, join keys, UTC rules, metric definitions, missing data, exclusions and examples.
- `manifest.json`: 26 diagnostic cases, reference SQL and Python-calculated expected rows.
- `provenance.json`: file hashes, row counts, context version/hash and source-preservation record.

All records describe a fictional product, Beacon; no customer data, credentials or external databases were used. No current workspace selection or customer file was changed.

## How the join actually works

Veyra currently selects **one SQLite file** per workspace. It does not federate two uploads or automatically apply a context document. The adapter opens one read-only connection and denies ATTACH. This test does not weaken those boundaries or implement federation.

The development generator creates two source snapshots, reads both read-only, and inserts their rows into a **new** `joined.db`. It declares and validates these relationships there:

```text
activity_log.actor_id     -> people.person_id
activity_log.workspace_id -> accounts.account_id
invoices.workspace_id     -> accounts.account_id
memberships.person_id     -> people.person_id
memberships.account_id    -> accounts.account_id
```

Cross-source IDs in product.db are plain columns, not broken foreign keys pointing to tables absent from that file. Cross-source FKs exist only after combination. Both source hashes remain unchanged. Joined data equals the original source rows, and SQLite integrity/foreign-key checks pass.

To try it in the UI, upload/select `joined.db` through the existing database settings, then ask questions on that selected snapshot. Uploading/selecting crm.db and product.db individually does **not** join them. The test itself did not activate any of these files.

## Recorded context and how it was delivered

The completed brief specifies, among other things:

- Customer/workspace means accounts; user/actor means people. Membership is not activity. An event ID is not a person ID.
- “Opened the app” maps to action `app_open`; active user means a distinct known actor with that action in the requested period. Sign-in alone does not qualify under this demo definition.
- Group activity through its own workspace ID, not every membership of the actor. Membership joins would duplicate or misattribute events for multi-account people.
- Paid recorded revenue is signed USD cents, including refunds and zero, excluding voids; unknown amounts are not known zero. Plan grouping excludes unattributed workspaces and uses the current account plan, not historical plan.
- Reporting is UTC with half-open month bounds. Offset timestamps can cross the March/April boundary.
- Daily active results are sparse: exclude unknown actors before grouping and emit only dates with known qualifying actors. No anonymous-only zero buckets or complete-calendar series.
- Conversion is ordered app_open then export for the same known actor, across all workspaces/all available dates, permitting equal timestamps. Retention, activation and sessions are deliberately undefined and must clarify.

The service received **only each question and discovered schema/profile**, not the context document, SQL references or expected answers. For testing, explicit questions were manually authored from the contract. There were 12 raw/explicit pairs plus two write refusals. Raw wording that required an unavailable business definition/mapping was labeled clarification, not answerable. Four raw control questions were self-contained and answerable. Consequently raw and explicit groups have different information/denominators and **cannot be presented as a context-feature accuracy gain**.

## Results on the reviewed snapshot

Deterministic mode; examples/model generation disabled. All 26 references computationally verified before scoring using independent Python collection/UTC calculations versus reference SQL execution. This is not independent human review or a held-out evaluation.

| Metric | Result |
|---|---:|
| Exact answerable query results | 12/15 |
| Executed answerable queries | 13/15 |
| Correct overall outcomes | 23/26 |
| Wrong executed answers | 1 |
| Unnecessary clarifications | 2 |
| Expected clarifications | 9/9 correct |
| Write refusals | 2/2 correct |
| Exceptions / unsafe attempts | 0 / 0 |

All **six answerable cross-source join cases** were correct (four distinct join intents, some with paired wording). They cover revenue/plan grouping, activity/plan grouping, no activity and no paid invoices. This small success is not general arbitrary-join accuracy.

For the 12 explicit questions: eight of 11 answerable requests were exact, one executed incorrectly and two were withheld; the remaining undefined-retention question correctly clarified. All four self-contained raw queries answered correctly and eight raw requests lacking configured mappings/definitions clarified. This is **not 12/12 successful raw SQL answers**.

### Confirmed remaining error

`joined-03-explicit`: “Count activity_log whose action is app_open during March 2026” returns **7 instead of 8**. Generated SQL compares timestamp strings lexically; the reference normalizes UTC offsets. The new fixtures make the offset counts unequal so this cannot pass by coincidence. The observed SQL mismatch is confirmed; no production fix was implemented in this testing task.

### Withheld requests

- Explicit sparse daily active counts with missing actors excluded: the current activity grammar does not support the supplied exclusion phrasing.
- Explicit ordered conversion: the planner correctly avoids an unordered/simple-count substitute, but the requested ordered operation remains unsupported.

## Context review history

Original artifacts under `datasets/test-packs/joined-context-v1/` and `logs/joined-context-v1-*.json` remain preserved. In revision 1, daily results included anonymous-only zero-count dates while the Python reference expected only dates with known active actors. The document/question had not fully specified that bucket policy, so this difference should **not** be confidently attributed to a planner defect alone.

Context revision 2 explicitly states the sparse-bucket policy and adds the missing-ID exclusion to the daily question, then uses a new snapshot/report. The planner now withholds that request. The changed question means this is a **reviewed diagnostic revision**, not the same frozen evaluation or a measured planner improvement. No application/planner code changed between runs. Both runs score 23/26 overall, but revision 1 has two result mismatches/one withheld query and revision 2 has one wrong execution/two withheld queries. Clearer context does not implement missing SQL operators or guarantee correct interpretation.

## Verification, evidence and reproduction

Evidence: `logs/joined-context-v1-reviewed-evidence.json`, with every question, generated/reference SQL, expected/actual rows, context hash and per-group outcomes. Original service report: `logs/joined-context-v1-reviewed-deterministic.json`.

Verification: **267 backend tests passed**, including five new demo-integrity tests; **three frontend tests**, TypeScript and ESLint passed. One existing Starlette/httpx deprecation warning remains. The original development suite stays **64/90 exact, 82/108 overall**, with zero previous-pass regressions; canonical **58/58** and prior cross-schema **32/32** also pass. Production file fingerprints are unchanged. Do not blend those denominators with this small context diagnostic. Source code and tests: `scripts/build_joined_context_demo.py`, `scripts/report_joined_context_demo.py`, `backend/tests/test_joined_context_demo.py`. The added tests cover oracles, source equality/preservation, declared cross-source keys, reproducibility/no overwrite, UTC/membership counterexamples and context-delivery disclosure.

```powershell
.\.venv\Scripts\python.exe scripts/build_joined_context_demo.py --output datasets/test-packs/my-joined-context
.\.venv\Scripts\python.exe scripts/run_independent_evaluation.py --pack datasets/test-packs/my-joined-context --verify-only
.\.venv\Scripts\python.exe scripts/run_independent_evaluation.py --pack datasets/test-packs/my-joined-context --systems deterministic --output logs/my-joined-context.json
.\.venv\Scripts\python.exe scripts/report_joined_context_demo.py --pack datasets/test-packs/my-joined-context --report logs/my-joined-context.json --output logs/my-joined-context-evidence.json
```

Choose new paths; existing files are not overwritten. Generator code reproduces the reviewed context revision, not the historical revision-1 question. SQLite files and logs are intentionally Git-ignored but reproducible from source. Final reserved artifacts, receipts, answers and construction logic were not opened, executed, regenerated or used. Ordinary source fingerprinting hashes script bytes without exposing final answers. All new data/context/questions are development-exposed and not eligible for held-out claims.
