# Evaluation

Evaluation runs 58 distinct query cases against the active database. References are independently written SQL, not generated planner SQL. Result multisets are compared without column aliases or row ordering. Cases include counts, grouping, temporal filters, event phrases, joins, exact-day retention, conversion, cohorts, experiment assignments and refusal/clarification requests.

Optional direct-LLM and schema-aware baselines execute through the same read-only safety boundary. Baselines are explicitly marked not run when the local model is unavailable or disabled. No score is fabricated. Runs can take several minutes with model baselines enabled.

Per-case wall latency, baseline inference latency, validated/executed syntax status, error text and correctness are reported. Correction counts and success counts are summarized. Python peak traced allocations are measured; this is not total process RSS and may include concurrent requests. Metric mathematics has dedicated backend tests. Scores are specific to the active database and model configuration. Open Evaluation and run the benchmark; cases are defined in `backend/app/metrics/evaluation.py`.

For an exported report, run `python scripts/run_benchmark.py --output logs/benchmark-report.json` from the repository root. The script refuses to overwrite existing output. Add `--include-models` for available Ollama baselines. Separate VEYRA inference time and total process RSS remain uninstrumented.

