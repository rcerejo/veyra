# Demo database schema

- `users`: signup date and acquisition, country, and device dimensions.
- `sessions`: bounded visits with explicit start/end timestamps; references `users`.
- `events`: typed product activity tied to both a user and session.
- `orders`: purchase revenue and timestamp; references `users`.
- `experiments`: experiment registry and date range.
- `experiment_assignments`: one variant assignment per experiment/user pair.

All generated timestamps are UTC ISO-8601 strings. The generator uses seed `20260115` and accepts a bounded user count. Its distributions introduce channel, geography, device, engagement, funnel, and revenue variation without asserting causal findings.

VEYRA can also upload and activate unfamiliar SQLite files from Settings. Uploaded data is not committed to Git. Schema Explorer reads metadata and bounded categorical samples from whichever database is active.

