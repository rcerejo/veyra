# Different schemas and model adaptation

## Generate the diagnostic databases

From the repository root on Windows:

```powershell
.\.venv\Scripts\python.exe scripts/generate_test_datasets.py
.\.venv\Scripts\python.exe scripts/evaluate_dataset_pack.py --output logs/schema-diagnostic.json
.\.venv\Scripts\python.exe scripts/prepare_sql_learning.py
```

Existing output directories and reports are never overwritten. To repeat generation use `--output` with a new directory, and pass that directory with `--pack` to the other scripts. The default source for the renamed copy is `datasets/veyra.db`; generate the standard demo first if it is absent. The source and active workspace are not modified.

Five SQLite files appear under `datasets/test-packs/v1` and can be selected in Settings:

| Family | Purpose |
|---|---|
| Commerce | Customers, purchases and refunds; amounts stored in integer cents |
| Subscriptions | Accounts, memberships and activity using unfamiliar action names |
| Support | Tickets, agents and messages; explicit joins and nullable resolution times |
| Messy | Mixed/ambiguous date formats, missing values, negative values and ambiguous customer tables |
| Renamed demo | Identical data with renamed tables/columns and preserved foreign keys |

The first four contain 1,520 rows total; the fifth copies the standard demo snapshot. All files pass SQLite integrity checks. The manifest contains 32 questions, independent expected answers and reference SQL, plus cases where clarification is the correct outcome. The evaluator verifies reference SQL against the independent answers before scoring. It compares complete result multisets, preserving duplicate rows and allowing small floating-point differences.

The initial diagnostic run scored 23/32. Fixes to schema-specific routing, value filters, metric clarification and date validation raised this to 32/32. These cases informed development: this is a regression score, not an untouched final generalization test. Date checks inspect a bounded sample of 1,000 non-null values and do not certify an entire column's cleanliness.

## Verified examples, not weight training

The learning exporter writes:

- `train.jsonl`: 33 conversational training rows representing 11 SQL queries and templated paraphrases.
- `fewshot.jsonl`: 11 verified question/schema/SQL patterns for local prompt retrieval.
- `heldout.jsonl`: 19 diagnostic cases from subscription, messy and renamed schemas, excluded from the prompt/training export.
- `clarifications.jsonl`: two training-family clarification cases exported separately for review, not mislabeled as SQL targets.
- `split-report.json`: provenance, family splits and explicit limitations.

Commerce and support are the training families. All paraphrases of a query stay together. The other families are held out from the training/prompt corpus, but were inspected during query-engine development; do not present them as blind testing. A genuine final evaluation needs additional unseen schemas and questions created after the design is frozen.

This small, repetitive corpus is a starting point. It does not justify claims of reliable fine-tuning. Before updating weights, add substantially more distinct verified queries, join patterns, nested aggregations and human-reviewed paraphrases; retain whole-schema holdouts and compare the unchanged base model against the adapted one.

## Test the installed local model

First inspect `ollama list`, then explicitly choose an installed model. For example:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_dataset_pack.py --with-model --model llama3.1:8b --family subscriptions --limit 1 --output logs/model-baseline.json
.\.venv\Scripts\python.exe scripts/evaluate_dataset_pack.py --with-model --model llama3.1:8b --family subscriptions --limit 1 --examples datasets/test-packs/v1/learning/fewshot.jsonl --output logs/model-examples.json
```

Model-preferred runs retain mandatory clarification guards. If the requested model is unavailable, offline SQL can still run; inspect each case's `source` before claiming a model result. Increase `--limit` or omit it to run more cases, allowing for CPU latency. The verified local smoke test used Ollama in both modes and returned the correct count in both. One question provides no evidence that the examples improve model accuracy, and its latencies cannot be compared fairly because of warm-up.

To opt into example-assisted model SQL in the app, configure the repository-root `.env`, then restart:

```dotenv
VEYRA_OLLAMA_MODEL=llama3.1:8b
VEYRA_SQL_EXAMPLES_PATH=datasets/test-packs/v1/learning/fewshot.jsonl
VEYRA_PREFER_MODEL_SQL=true
```

Only set the model to one installed on your machine. Model-preferred generation is experimental; the default remains deterministic/schema-derived compilation. Generated SQL still goes through validation and read-only execution. Missing business definitions, ambiguous tables and detected mixed dates still require clarification.

## Fine-tuning later

No model weights are trained by these scripts. This machine exposed Intel integrated graphics and no NVIDIA training GPU. CPU training is possible in some setups but was not started. GPU fine-tuning requires a separate training environment, a suitable base model/license, reviewed data, and an explicit compute plan. Do not install a large training stack into the app's pinned runtime merely to run a demo.

The conversational JSONL format can be used with [Hugging Face TRL's SFT workflow](https://huggingface.co/docs/trl/sft_trainer). An inference runtime such as [Ollama imports separately prepared model weights](https://docs.ollama.com/import); importing or creating an Ollama model is not itself supervised training. Do not publish the synthetic diagnostic score as a fine-tuned-model result.
