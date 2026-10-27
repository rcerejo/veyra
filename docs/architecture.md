# Architecture

VEYRA separates probabilistic generation from trusted execution. The frontend sends only a natural-language question. FastAPI validates it, creates a typed plan, discovers only the active database schema, and chooses either a deterministic compiler or the configured local model. Generated SQL is never trusted: SQLGlot must parse it as one read-only query referencing known tables, after which SQLite runs it through a read-only connection and an authorizer with progress and result limits.

The database adapter contract isolates schema discovery and query execution so a PostgreSQL implementation can be added later. The `SchemaCatalog` represents explicit foreign keys and can find join paths; it never treats similarly named fields as proof of a relationship.

The database registry confines selectable files to the local `datasets` directory. Uploaded files must use a supported SQLite extension, pass the SQLite header check, remain under 100 MB, and are stored under `datasets/uploads`. The active database is persisted as a relative path, preventing arbitrary filesystem access.

Schema profiling samples only bounded values from likely categorical text columns. Columns with names indicating credentials or personal information are excluded. These samples help the local model connect phrases such as “opened the app” to stored values such as `app_open` without turning the LLM into an execution authority.

The semantic planner uses lexical schema matching, sampled-value evidence, relative or explicit calendar windows, and explicit foreign keys to compile common lookups and aggregations without a model. Ambiguous matches produce focused clarification options. Questions outside deterministic coverage can use Ollama; generated SQL is checked for statement type, tables, and columns, and rejected SQL receives at most two bounded correction attempts before the request fails safely.

Failure is an expected state. When Ollama is unavailable, supported deterministic questions remain functional. Unsupported questions return a clarification response rather than invented SQL or data.

The compositional path also supports bounded typed relationship-existence predicates. Participation and absence compile to correlated EXISTS/NOT EXISTS rather than fanout-prone outer joins. The inner path uses explicit foreign keys, retains composite correlations, and withholds ambiguous roles, competing paths and ungrounded conditions. SQLGlot coverage checks include the complete subquery. See [existence increment and measured development results](existence-planner-v1.md).

Product metrics use a separate deterministic path. Each definition names its formula and required fields, and the activity service emits DAU, WAU, and MAU on UTC calendar boundaries plus windowed session metrics. An uploaded database that lacks the canonical product fields receives a compatibility error; VEYRA does not ask a model to invent mappings for trusted metrics.

## In-app source combination

`DatabaseCombiner` adds a bounded source-inspection/materialization path, separate from read-only query execution. Explicit cross-source keys become validated FKs in a new namespaced SQLite snapshot, with creation provenance; activation is a separate existing registry operation. Source DBs and query ATTACH/write restrictions are unchanged. See [multi-source snapshots](multi-source-snapshots.md) for API/UI contracts, limits and tests. This is not live federation, automatic semantic mapping or tenant isolation.

