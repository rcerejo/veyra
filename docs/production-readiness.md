# Production readiness assessment

Status: hardened local/private-workspace prototype. Not approved for public or multi-customer deployment.

## Highest priority blockers

1. Identity and authorization: there are no individual users, roles or workspace permissions. Production mode now requires a constant-time checked gateway credential. This is service-to-service protection, not user login. An authenticated reverse proxy must validate company identity, authorize workspace access, strip client-supplied X-Veyra-Key and inject the secret upstream. Never put this key in browser JavaScript, localStorage or a public nginx configuration. Keep the API unreachable except from the authenticated gateway. Credential rotation and logout belong to the identity layer.
2. Workspace isolation: `.active_database` selects a single shared workspace globally. One user's switch affects everyone. Multi-customer service requires tenant-scoped metadata, storage, query context, authorization and isolation tests before onboarding customer data. Multiple workers do not solve this.
3. Workload isolation: ML training, benchmarking and schema profiling are expensive. A per-process admission limit and SQL timeouts are first safeguards, not distributed quotas. Production should disable web administrative jobs and run them through a queue with worker CPU/memory/time limits, cancellation and per-workspace quotas. Snapshot database identity at job submission. Profile/schema discovery still needs load testing.
4. Data protection and recovery: uploads need quotas, retention policies and isolated processing of untrusted SQLite files. New checks validate integrity, bound request/response sizes and disable trusted schema behavior; parsing an uploaded file inside the API process is not a hardened sandbox. Add encrypted durable storage, off-machine backups and demonstrated restore drills. Do not run customer production data from a OneDrive folder.
5. Deployment and operations: serve built frontend assets over HTTPS behind the authenticated gateway, not Vite's development server. Provision secrets, health/readiness probes, monitored structured logs, alerting, disk limits, dependency scanning and rollback. Liveness does not prove database/model readiness. Container configuration has been supplied but cannot be certified until built and tested on the target platform.
6. Analytical correctness: 58 demo reference cases and backend tests are useful, not sufficient release evidence for arbitrary customer schemas. Establish explicit metric mappings, historical attributes, timezone/currency contracts, observation watermarks, representative real-data tests and browser regression coverage. A high synthetic-model score is not proof of production prediction quality.

## Implemented hardening

- Production refuses missing/short gateway secrets, wildcard/test hosts and non-HTTPS cross-origin origins.
- Workspace API endpoints require the gateway credential when configured. Public `/livez` reveals no workspace data.
- Trusted Host middleware, no-store API responses, request IDs, method/status/duration logs without request bodies or credentials, and generic unexpected error responses.
- Per-process request admission limit; default four workspace requests. This is not per-user rate limiting.
- Upload size is enforced while receiving chunks; other request bodies are limited to 1 MB.
- Uploaded database integrity check with a deadline, exclusive upload filenames and cleanup of rejected files. Workspace selection uses atomic replacement.
- Explicit SQLite connection closure fixes lingering file handles. Read-only URI handling supports special filename characters. Trusted schema and extension loading are disabled, SQL/value sizes and aggregate response bytes are bounded.
- Pinned tested Python dependency snapshot, existing frontend lockfile, CI definition and non-root API container recipe.
- Upgraded ECharts to 6.1.0 with its compatible React wrapper and pinned DOMPurify to 3.4.17 to address the advisories found in the installed production dependency tree. The post-upgrade registry audit endpoint failed with connection resets; a successful full re-audit remains a release gate, not an assumed clean result.

## Private-workspace deployment contract

Use `.env.production.example` as a template. Supply the gateway secret through the platform secret manager, explicit allowed hosts and an empty CORS list for same-origin hosting. Set `VEYRA_ENABLE_ADMIN_JOBS=false`. Route `/api/*` through an identity-aware gateway. Static frontend fetches remain same-origin and never receive the gateway secret. Restrict network access to the API and Ollama. Do not rely on CORS as authentication.

Build the API from repository root: `docker build -f backend/Dockerfile -t veyra-api .`. The data volume must be owned by UID 10001. Use one API worker until shared-state design and workload budgets are addressed. Apply external request-body size/read time limits, rate limits and TLS at the gateway. Run with read-only root filesystem, a temporary directory mount and an explicitly permissioned durable `/data` mount. The container base tag and CI action tags should be pinned to reviewed digests before a controlled release.

Required acceptance evidence: authentication bypass tests, workspace-isolation tests where relevant, target-platform image build and smoke test, load test with mixed queries/uploads, bounded-job tests, successful backup restore, dependency/security scan and a clean staging rollout/rollback. Until these pass, this repository should not be called production-ready.
