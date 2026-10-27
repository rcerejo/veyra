# In-app multi-source datasets (first version)

Veyra can now combine **2–5 local SQLite sources inside the app**, with explicitly defined cross-source keys, and query the resulting dataset. Users no longer need to pre-merge their files. This is **snapshot materialization**, not live federation: source updates do not appear until a new snapshot is created.

## Using Settings

1. Upload both source databases using the existing Upload database action. Uploads still use the existing validation/selection behavior.
2. Under **Combine uploaded databases**, select the sources. Inspect their table lists and give them meaningful prefixes, such as `crm` and `product`.
3. Add child → parent relationships using the actual keys. Parent columns must be an exact declared primary/unique key; use Add composite-key pair when necessary. Every selected source must connect to the others through explicit mappings.
4. Name the snapshot and confirm the mappings. **Create combined dataset** validates/copies the data but does not change the active selection.
5. Review the source fingerprints, row counts and mappings, then click **Connect combined dataset**. Ask Veyra and Schema Explorer now use the snapshot. **Snapshot details** retrieves verified creation metadata later, including after a page reload.

If running without backend reload, restart the backend to load the new routes, then refresh the frontend. This development task did not restart services or switch the user's running workspace.

For the supplied Beacon demo, upload `crm.db` and `product.db` from `datasets/test-packs/joined-context-v1-reviewed/` and define:

| Child source/table/column | Parent source/table/column |
|---|---|
| product.activity_log.actor_id | crm.people.person_id |
| product.activity_log.workspace_id | crm.accounts.account_id |
| product.invoices.workspace_id | crm.accounts.account_id |

Internal CRM membership FKs are preserved automatically. Do not link events through every membership: that changes their grain and may misattribute or multiply rows. NULL foreign keys are permitted; non-NULL orphan keys fail validation and **no rows are silently dropped**.

Tables are always namespaced (`crm__accounts`, `product__activity_log`), so identical original table names remain distinct. The schema inspector and creation result show exact output names. Supported example questions:

```text
Count product__activity_log by crm__accounts plan
Total paid product__invoices usd cents by crm__accounts plan
List crm__accounts without product__activity_log
List crm__accounts with no paid product__invoices
```

Selecting key relationships does not approve metric definitions, attach a context document, or make every natural-language query supported. Existing canonical cohort/funnel/experiment services retain their required-table contracts; namespaced sources do not automatically become compatible canonical metric tables. The semantic mapping layer remains separate future work. Known UTC-filtering and unsupported ordered-funnel issues from the previous context test are not fixed by this feature.

## Architecture and safeguards

Plan implemented incrementally: inspect sources without changing selection; validate typed mappings; materialize a new snapshot; persist provenance; expose explicit creation/connection controls; test constraints and unchanged query behavior.

- `DatabaseRegistry.resolve_source` confines paths to the local workspace, validates SQLite input and size, and does not activate it. Path escapes and staged files are rejected. In-progress `.veyra-combine-*` directories do not appear as selectable databases, including resolved paths through aliases.
- `DatabaseCombiner` uses read-only source connections and SQLite backup to capture committed WAL data. Private copies normalize journal mode to avoid lingering WAL/SHM sidecars during publication. Each source capture is consistent individually; this is **not a distributed transaction** across live sources.
- User-provided SQL is not accepted. Identifiers are quoted; source CREATE TABLE SQL, views, triggers and extension code are not executed. Ordinary table columns, declared types, values, primary keys, plain unique keys and existing FKs are reconstructed. Generated/hidden columns, virtual tables, strict tables, collations, partial/expression unique indexes and unsupported type declarations fail closed.
- Cross-source links must reference existing columns with compatible declared type affinities, match an exact unique parent key and connect the selected sources. Duplicate mappings fail. These are explicit many-to-one/one-to-one identity links, not arbitrary many-to-many SQL joins; many-to-many relationships need a real bridge table.
- Row copying preserves original fact rows. After copying all tables (including cyclic relationships), foreign-key and integrity checks must pass. Invalid mappings, resource failures or unsupported schemas publish no selectable result; temporary files are cleaned. Creation never activates a result.
- A completed directory is published under `datasets/combined/<name>-<uuid>/`, with `dataset.db` and `dataset.provenance.json`. There is no overwrite/delete/update operation on existing source or generated snapshots through this workflow. The filesystem owner can still modify files outside the app.
- Windows testing reproduced intermittent WinError 5 at the completed-directory rename. Publication now retries only Windows sharing/access-denied errors (5/32/33), at most ten attempts within the existing deadline, rechecking destination absence each time. Unknown permission failures are not retried. Persistent locks fail with a useful error and no activation. Fault-injection tests cover recovery, permanent failure and non-overwrite; three consecutive focused reruns passed after the fix.
- Existing SQLGlot and SQLite read-only enforcement are unchanged. The query connection still denies ATTACH, writes and extension loading. Joining happens through the explicit FKs in the prepared snapshot, not by allowing arbitrary filesystem SQL access.
- New endpoints inherit the existing gateway credential, request-body limit and request concurrency boundary. This remains a **single private/local workspace feature**, not authenticated multi-tenant isolation. No public customer access was enabled.

Defaults/check constraints, views/triggers, non-unique indexes and original DDL operational semantics are not copied. The result is an analytical data snapshot, not a complete executable database migration or writable application replacement. Ignored views/triggers and limitations are disclosed. No coercion or automatic join inference is used to force incompatible data through.

Limits: 100 MB per source capture, 200 MB captured sources total, 100 MB output, 60 tables, 100 columns/table, 500,000 rows total, 1–32 new relationships, up to four columns per new relationship, 30-second build budget, and per-value length bounds. SQLite validation/discovery also has its own deadlines; this is not a hard real-time SLA or a large-data distributed engine. Temporary copies use extra disk space. Refresh requires a new snapshot; incremental sync, cancellation/job queues and automatic source-change tracking remain unimplemented.

## API

- `GET /api/databases/schema?name=uploads/crm.db`: structural preview and declared unique keys; does not change selection.
- `POST /api/databases/combine`: typed source/key mappings; returns 201 with inactive `database`, `provenance`, and `provenance_sha256`.
- `GET /api/databases/provenance?name=combined/.../dataset.db`: reads persisted creation metadata and checks the dataset fingerprint. This is not a signed/tamper-proof audit record. Query responses do not automatically attach all snapshot metadata; fetch provenance for reproducibility.
- Existing `POST /api/databases/activate`: explicit activation after review.

```json
{
  "name": "beacon-workspace",
  "sources": [
    {"name": "uploads/crm.db", "alias": "crm"},
    {"name": "uploads/product.db", "alias": "product"}
  ],
  "relationships": [{
    "child_source": "product", "child_table": "activity_log", "child_columns": ["workspace_id"],
    "parent_source": "crm", "parent_table": "accounts", "parent_columns": ["account_id"]
  }]
}
```

For the full Beacon identity graph add the actor and invoice mappings listed above. Paths are registry-relative filenames, never arbitrary absolute paths. Invalid typed requests/mappings return 422 with a useful error. No active dataset changes on a failed build.

Creation metadata includes individually captured source names/aliases, snapshot hashes/times, output table names, row counts, explicit cross-source relationships, combined-file hash and limitations. No raw customer values are logged or included in this metadata. Internal FKs are present in the combined schema. Snapshot hashes identify captures, not a promise that separately changing sources were captured at the same instant.

## Verification and measured outcomes

**307 backend tests passed** (40 new), **15 frontend tests passed** (12 new); TypeScript, ESLint and the production Vite build passed. Existing Starlette/httpx deprecation and large-bundle warnings remain. Frontend tests cover API payloads, configuration validation and initial UI markup; no full browser interaction test is claimed. Final backend result: `logs/combine-v1-backend-final.xml`.

Backend tests cover explicit unique keys, composite keys with reused component values, repeated builds, namespace collisions, NULLs, orphan rejection without dropped rows, mismatched types, unknown/missing fields, disconnected sources, unsupported schema semantics, quoted identifiers, row/time budgets, cleanup, WAL commits, source preservation, metadata verification, hidden staging, gateway protection and continued write/ATTACH rejection. Real API handler tests cover inspect/create/review/activate/query.

An additional isolated in-process walkthrough uploads the two Beacon sources, creates/reviews/connects the snapshot and runs **four selected cross-source NL queries: 4/4 exact**. References come from Python operations on synthetic source records, not generated SQL. Final output: `datasets/test-packs/in-app-combine-v1-final/api-walkthrough.json`, with configuration, created dataset metadata, SQL, expected/actual rows and source hashes. This proves that selected workflow, **not arbitrary join correctness or general NL accuracy**, and does not change the running workspace. Earlier walkthrough artifacts are preserved separately.

Regression evaluations remain unchanged:

| Development suite | Result |
|---|---:|
| Original 108 cases | 64/90 exact queries; 82/108 overall |
| Canonical | 58/58 |
| Prior cross-schema | 32/32 |
| Synthetic stress, seed 11 | 50/78 exact; 62/90 overall |
| Synthetic stress, seed 29 | 50/78 exact; 62/90 overall |
| Reviewed context diagnostic | 12/15 exact; 23/26 overall; one wrong UTC answer and two withheld queries remain |

Final reports: `logs/combine-v1-original108-final.json`, `logs/combine-v1-canonical58-final.json`, `logs/combine-v1-crossschema32-final.json`, `logs/combine-v1-stress-seed11-final.json`, `logs/combine-v1-stress-seed29-final.json`, and `logs/combine-v1-context-regression-final.json`. Earlier reports without the `final` suffix predate the final publication-lock fix and remain preserved. This feature adds a source-combination workflow, not measured NL accuracy improvement. All these cases are development-exposed; reserved final archives/receipts/answers/construction logic were not opened, executed, regenerated or used. Normal source fingerprinting hashes script bytes without exposing final answers.

Reproduce the isolated API walkthrough with a **new** output directory:

```powershell
.\.venv\Scripts\python.exe scripts/demo_database_combination.py --output datasets/test-packs/my-in-app-combine
```

Requires the previously generated reviewed Beacon source pack and development testing dependencies. It uses an isolated in-process server, not the currently running browser/server. Relevant implementation: `backend/app/database/combine.py`, database request schemas/API routes/registry, `frontend/src/components/CombineDatabasesPanel.tsx`, Settings, API types/client and tests. No existing working planner modules were rewritten.
