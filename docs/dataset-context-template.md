# Dataset context brief

Use this brief to explain an unfamiliar dataset to the developer/analyst configuring Veyra. Fill in only what is known; mark unknown definitions as unknown. Do not include credentials, customer records, emails, or other personal data. Schema DDL, fabricated examples and approved aggregate outputs are usually sufficient.

**Current limitation:** this is a human-readable configuration brief, not an implemented upload format or automatically loaded prompt context. Veyra currently discovers schema/FKs and sample categories, but does not yet persist and apply approved semantic mappings. Merely filling in this file does not change query behavior. A validated mapping workflow must be implemented before definitions can safely drive arbitrary analytics.

## 1. Dataset and business meaning

- Business/domain:
- Database snapshot/version and schema version:
- What questions should this dataset answer?
- What is outside scope or unavailable?

## 2. Tables and grain

For each relevant table:

```text
Table:
One row represents:
Primary/unique key (including every composite-key column):
User/customer identity field, if any:
Related tables and exact key pairs:
Relationship cardinality (one-to-one / many-to-one / many-to-many):
Role distinctions (e.g. actor versus reviewer, buyer versus account owner):
Duplicate records, orphan relationships, soft deletion and NULL policy:
```

Include schema DDL or a schema export. Names alone are insufficient: an event ID is not a user ID, and membership is not evidence of activity. Do not guess relationships because two columns have similar names.

## 3. Column and event vocabulary

```text
Source column / catalog key:
Business meaning:
Storage type and unit:
Allowed values:
Human phrases / synonyms that mean this value:
Example: “opened the app” means event_kinds.label = app_open,
         joined through usage_events.kind_id = event_kinds.kind_id.
Terms that must NOT be treated as equivalent:
```

Aliases explain vocabulary; they are not authorization to invent a metric definition or a join.

## 4. Time contract

- Timestamp role for each operation (event occurrence, ingestion, signup, payment, assignment):
- Storage representation and timezone:
- Reporting timezone; daylight-saving convention:
- Date-only meaning and inclusive/exclusive boundaries:
- Week start and definition of “last seven days” (rolling hours versus complete days):
- Late-arriving records; data-complete-through timestamp:
- Missing/invalid date policy:

Veyra's current bounded temporal planner uses UTC and Monday-start weeks where supported. A different business timezone in this brief is a requirement to implement/validate, not an existing supported setting.

## 5. Explicit metric definitions

For each metric supply: source rows, qualifying filters, identity, aggregation, denominator, time anchor/window, exclusions and missing-data handling.

```text
Active user:
Revenue (amount unit, currency, refunds, recognition date):
Activation (qualifying action and window after what anchor):
Retention (cohort entry, return activity, exact-day/rolling rule, maturity cutoff):
Conversion (ordered stages, identity/scope, equal-time policy, window, denominator):
Session (provided identifier or explicitly defined inactivity rule):
```

Do not supply a definition just to make every field look complete. An unknown definition should trigger a targeted clarification. Existing canonical workflows still require their supported schema contracts; these descriptions alone do not make an unfamiliar schema compatible.

## 6. Reviewed examples and counterexamples

Provide 5–10 representative business questions with the intended interpretation. Approved SQL and aggregate expected results are especially useful, if available. Include counterexamples: duplicate events should not double-count users; export-before-open should not qualify for an ordered conversion; unknown dates should not become evidence of inactivity.

```text
Question:
Entity/measure:
Filters and time window:
Grouping/order:
Expected interpretation or approved read-only SQL:
What a plausible but wrong answer would do:
```

Any examples used to develop Veyra become development examples, not a held-out evaluation set. Keep a separate final set untouched.

## Per-question checklist

A user should not need to provide all this with every question. Once approved mappings exist, the platform should reuse dataset definitions and ask only for unresolved choices. Until then, a precise request looks like:

> Count distinct actor IDs from usage events whose catalog action is app_open, for March 2026 in UTC, grouped by UTC date. Count each actor once per day, exclude missing actor IDs/dates, and do not count mere account registrations.

No amount of context guarantees perfect interpretation. Typed planning, identifier/type validation, preserved-operation checks, reference tests, result provenance and clarification remain necessary.
