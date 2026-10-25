# Architecture

VEYRA separates probabilistic generation from trusted execution. The frontend sends only a natural-language question. FastAPI validates it, creates a typed plan, discovers only the active database schema, and chooses either a deterministic compiler or the configured local model. Generated SQL is never trusted: SQLGlot must parse it as one read-only query referencing known tables, after which SQLite runs it through a read-only connection and an authorizer with progress and result limits.

The database adapter contract isolates schema discovery and query execution so a PostgreSQL implementation can be added later. The `SchemaCatalog` represents explicit foreign keys and can find join paths; it never treats similarly named fields as proof of a relationship.

Failure is an expected state. When Ollama is unavailable, supported deterministic questions remain functional. Unsupported questions return a clarification response rather than invented SQL or data.

