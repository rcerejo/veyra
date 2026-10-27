# Using the local preview

Veyra is a single-person local analytics preview, not a hosted service. Do not bind the development servers to public interfaces or share the workspace with other users. No public deployment or customer adoption is claimed.

## First session

1. Follow the root README quick start. Keep the launcher terminal open; Ctrl+C stops both servers.
2. Open Ask Veyra and use one of the row-count questions discovered from the connected database. These are starting points, not promises that every schema is supported.
3. Inspect the interpretation and generated SQL. “Read-only SQL checks passed” refers to technical validation, not a verified business answer.
4. For your own data, open Settings. Use a consistent SQLite backup/export with any WAL changes checkpointed by the exporting application, not a copy of a busy database file alone. Keep your original backup.
5. Remove sensitive fields where possible. Uploads are persisted locally, not automatically deleted when you close the app. Stop the app before manually removing unused uploaded files; do not delete the connected database without selecting another first.
6. Review Schema Explorer. The starter questions use actual table identifiers, not customer values. Specialized retention, funnel and experiment pages still require their documented product-table contracts. Arbitrary semantic mappings are not implemented.
7. To combine sources, upload each one, map keys explicitly in Settings, create the static snapshot, review it and connect it. Source updates do not refresh old snapshots.

## Reading an outcome

- **Results:** review the measure, distinct identity, joins, filters and dates before making decisions. Zero matching rows is a valid result, not an unavailable backend.
- **Partial results:** a row limit was reached. The CSV contains only returned rows; it is not a full database export.
- **Clarification:** no analytical answer is being provided. Edit the original question with table/field names, metric definitions and the year. Suggested questions are alternatives, not an answer to your original request.
- **Connection error:** check the launcher terminal and use Refresh status or Refresh database list. Do not start duplicate servers on occupied ports.
- **View failed:** open another page or reload. Reload loses unsaved forms. If an upload/snapshot was in progress, inspect Settings before retrying; the UI cannot guarantee that an interrupted view rolled an action back.

## Data and models

SQLite files remain on the local filesystem. If model generation is used, questions, schema and bounded sampled values may be sent to the configured Ollama endpoint. The default endpoint is local, but configuration can change that boundary. Do not send sensitive data without permission. Veyra does not automatically train a model on uploads. Runtime SQL inspection and fonts no longer require third-party CDN downloads; first-time dependency installation still needs internet access.

## Known limitations

Natural-language coverage is bounded. The 400-case development diagnostics still withhold 72 answerable executions; a separate context diagnostic has a known UTC-boundary wrong answer. Dates, custom business definitions and unsupported analytical operations need careful review. Synthetic development scores are not held-out generalization or production correctness guarantees. The final evaluation archive remains reserved.

Public deployment requires authentication, tenant isolation, secure storage, quotas, backup/restore verification and operational/security review. See `production-readiness.md`. This preview pass does not implement those systems.
