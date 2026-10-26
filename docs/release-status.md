# Release status

This is a runnable local product-intelligence prototype, not a completed implementation of every item in the original master outline.

## Implemented

- Natural-language SQLite querying, schema/value discovery, explicit FK joins, safety validation and bounded model correction
- Database upload/selection and schema explorer
- Engagement, exact-day signup retention, ordered conversion funnels
- Conversion experimentation, assignment diagnostics, relative/absolute effects, z-tests, Welch session guardrails and planning calculator
- Composition-aware conversion investigations
- Growth/revenue and acquisition summaries
- Logistic regression and random forest churn holdout evaluation; standardized K-means engagement clusters
- 58 reference-query benchmark cases with optional direct/schema-aware model baselines
- CSV result export, local launch/stop scripts and backend regression suite

## Remaining against the original outline

- Arbitrary schema-to-metric mappings and PostgreSQL support
- Subscription/product-category mappings and custom activation/churn definitions beyond the implemented purchase/inactivity contracts
- Free-text experimentation routing; investigation metrics beyond conversion, revenue and active users
- Benchmark coverage of advanced analytical questions, separate syntax/memory instrumentation and persisted evaluation history
- Sequential inference, multi-arm experiments, multiple-testing correction and configurable continuous guardrails
- Temporal model validation across multiple cutoffs and prediction serving
- Full automated browser regression suite, accessibility/responsive polish and production packaging

Observed model metrics use synthetic data and a fixed historical user split. They do not establish real-world predictive quality. Optional LLM benchmark results are absent until run against an available local model. Analytics modules require compatible product tables and do not infer semantic mappings from arbitrary schemas.
