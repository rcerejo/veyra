# Semantic mapping audit and next implementation contract

Status: design/audit only. No mapping API, persistence, projection adapter or approval UI is implemented by the independent-evaluation increment.

## Current behavior

`ActivityMetricService` declares canonical required fields in `ACTIVITY_DEFINITIONS` and checks them before calculation. Retention directly requires users.user_id/signup_date and events.user_id/event_timestamp. Funnels require the canonical events table and an explicitly supplied step list/window. Experimentation requires experiments, experiment_assignments and events, with an optional compatible sessions table. Growth and prediction also use canonical product fields. These checks are safety contracts, not a semantic mapping system.

`SchemaCatalog` discovers identifiers and explicit foreign-key paths. The NL semantic planner matches lexical names and sampled categorical values, but does not persist an approved business interpretation. The registry stores a globally selected database, not user/workspace-scoped metadata. The Settings page uploads/selects databases; Schema Explorer displays structure. Neither approves business definitions.

## Proposed minimal implementation

1. Store metadata separately from uploaded SQLite data, keyed by a database identity and schema fingerprint. A schema fingerprint alone must not cause mappings to be shared between unrelated databases.
2. Maintain immutable mapping versions with draft/approved state and a content hash. Approval must be an explicit action, not a default. Changed source schemas invalidate approval. Results include the approved mapping version/hash, resolved parameters and data snapshot identity; a mapping version alone cannot reproduce results from a mutable database.
3. Restrict initial mapping expressions to validated identifier references and allowlisted transforms; do not accept arbitrary user-provided SQL expressions. Define source grain, unique entity keys, foreign keys, duplicate handling, null policies, timestamp representation/timezone and observation watermark.
4. Support independently optional users, events, sessions and revenue sources. Map event identifiers/user/timestamp/type; normalized event catalogs require explicit validated joins. Sessions need explicit start/end units and user relation. Revenue needs amount scale, currency, refunds and recognition definition; do not silently combine currencies.
5. Activation needs a chosen qualifying event or rule and eligibility/window definition. Retention needs an anchor, qualifying activity, exact-day versus rolling definition and maturity cutoff. Conversion needs ordered/unordered steps, denominator, entry selection, timestamp tie handling and observation window. An unresolved concept stays unavailable rather than borrowing another database's definition.
6. Produce validated read-only canonical projections for compatible existing services, so their tested calculations can be reused. Check collision handling and never overwrite source tables. Mapped experimentation additionally requires experiment/assignment keys, variants, assignment time and explicit event/session relations; user/event mappings alone are insufficient.
7. UI: show source fields and relationships, missing requirements, proposed definitions and sample validation summaries without copying raw sensitive values into telemetry. Allow editing, explicit review/approval, version history and invalidation warnings. Do not call a draft compatible or enable a metric until all its requirements pass.

## Acceptance tests before activation

- Canonical versus mapped workflow parity on a development-only renamed fixture (never the frozen evaluation schemas).
- Missing/ambiguous fields, unsupported transforms, stale fingerprints, duplicate IDs, invalid timestamp representations, unapproved edits and currency conflicts fail closed.
- Retention denominators and funnel ordering/maturity are preserved exactly.
- Experiment assignments preserve one-user-one-variant grain and follow-up boundaries.
- Switching databases cannot reuse approval accidentally; source databases are never mutated.
- Approval persistence/reload and response provenance are tested end to end.

This is a local-workspace feature until authentication and tenant-scoped state are implemented. An approval button is a local analyst confirmation, not an authenticated governance or audit system.
