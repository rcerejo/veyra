# User-facing local preview pass

## Scope

Improve the existing runnable local project for another person to try, without rewriting analytics or changing the NL-to-SQL planner. Preserve the current dirty workspace, evaluation fingerprints and reserved final set. No hosting, remote publishing, dependency upgrades, user-data deletion or live workspace switching was performed.

## Implemented

- A reusable first-session panel in Ask Veyra links to the real Settings and Schema Explorer views and explains custom-schema limits.
- Starter questions use up to three discovered, syntactically simple table identifiers instead of assuming demo users/events. Sampled customer values are not put into those prompts. Exotic table identifiers produce no starter rather than unsafe generated prose.
- The header now identifies a local workspace, links to Settings and offers status refresh instead of a nonfunctional “Product Demo” dropdown. Missing backend health shows launcher/retry guidance.
- Clarification guidance distinguishes alternative prompts from answers. Results describe read-only SQL validation rather than a blanket correctness guarantee; partial CSVs and empty results are explained.
- Question input has a keyboard-visible focus ring, a 1,000-character bound matching the backend and a consistent minimum length for keyboard/button submission.
- SQL inspection uses a selectable, accessible code block with handled clipboard failures instead of runtime CDN editor loading. External Google Fonts imports were removed; system fonts work offline. The installed Monaco dependency remains in the lockfile but is not loaded by this view; no unnecessary dependency churn was introduced.
- Settings explains consistent SQLite exports/WAL, persistent local uploads, permissions, model endpoint exposure, metric-definition limits and static snapshot semantics. Extension/size/empty-file checks give immediate feedback; backend validation remains authoritative. Successful upload/activation feedback and a database-list refresh are provided.
- API errors handle connection failures, unreadable responses and structured validation errors consistently for uploads and other operations.
- A view-level error boundary provides recovery without claiming pending uploads/snapshots were rolled back. Unsaved-form loss on reload is disclosed.
- Keyboard-visible controls and reduced-motion styling were added. This is not a full accessibility certification.

## Verification and release gates

The pre-change backend run passes all 340 tests (`logs/user-facing-before.xml`). Frontend tests cover schema-derived examples, import validation, rendered onboarding/privacy text, empty results, recovery fallback and API errors. These are unit/static-render checks, not automated click-through or browser-layout coverage.

The post-change backend run also passes **340/340** (`logs/user-facing-after.xml`), with the existing Starlette/httpx deprecation warning. The expanded frontend suite passes **28/28**. No backend production module or planner was changed in this pass, and no NL accuracy improvement is attributed to UI work.

TypeScript, ESLint and the final Vite production build pass. The build still warns about a roughly 1.15 MB minified shared chart chunk (386 KB gzip); chart-library slimming and browser performance testing remain follow-up work. `git diff --check` passes. No fresh dependency security audit or clean-machine/platform certification was performed.

An attempt to open the local preview through the browser automation surface failed because the browser webview did not attach. No visual, keyboard or responsive browser acceptance is claimed. Before distributing a release, manually check desktop and narrow-screen navigation, first-run demo count, SQLite import/selection, SQL copy/CSV download, disconnected backend retry and unavailable-model behavior. Include a screen-reader/keyboard pass and a clean-machine setup test. Follow the root README; do not expose Vite publicly.

No new NL accuracy or hosted-production claim is made. Existing development scores remain historical evidence, not newly measured by this frontend pass. The separate UTC-boundary issue, bounded query coverage, arbitrary metric mappings, authentication, tenant isolation, data-retention automation and public deployment requirements remain unresolved. See `corrected-query-testing-v1.md` and `production-readiness.md`.
