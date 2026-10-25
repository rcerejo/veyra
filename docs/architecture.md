# Architecture

VEYRA separates probabilistic generation from trusted execution. The frontend sends only a natural-language question. FastAPI validates it, creates a typed plan, discovers only the active database schema, and chooses either a deterministic compiler or the configured local model. Generated SQL is never trusted: SQLGlot must parse it as one read-only query referencing known tables, after which SQLite runs it through a read-only connection and an authorizer with progress and result limits.

The database adapter contract isolates schema discovery and query execution so a PostgreSQL implementation can be added later. The `SchemaCatalog` represents explicit foreign keys and can find join paths; it never treats similarly named fields as proof of a relationship.

The database registry confines selectable files to the local `datasets` directory. Uploaded files must use a supported SQLite extension, pass the SQLite header check, remain under 100 MB, and are stored under `datasets/uploads`. The active database is persisted as a relative path, preventing arbitrary filesystem access.

Schema profiling samples only bounded values from likely categorical text columns. Columns with names indicating credentials or personal information are excluded. These samples help the local model connect phrases such as “opened the app” to stored values such as `app_open` without turning the LLM into an execution authority.

Failure is an expected state. When Ollama is unavailable, supported deterministic questions remain functional. Unsupported questions return a clarification response rather than invented SQL or data.

