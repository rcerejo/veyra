# Query benchmark

The fifty reference cases live in `backend/app/metrics/evaluation.py` and run through POST `/api/evaluation`. The Evaluation screen presents the measured per-case results. Optional model baselines use `?include_models=true` and require the configured Ollama model.

Results depend on the active database. The demo run during release verification achieved 50/50 for the current querying suite after correcting a country/count tokenization bug. This is not a claim of general natural-language accuracy. Advanced retention, experiment and cohort correctness is currently verified by dedicated tests, not represented in this benchmark score.

No direct-LLM or schema-aware score is published when the model is unavailable. No model-score comparison can be concluded from a VEYRA-only run.
