# MoniBox / HSC-RAG-DE Benchmarks

This package runs deterministic offline paper evaluations for clean and robustness
datasets. The default profile is `profiles/paper_eval.yaml`, which uses the null
LLM backend and disables speech/hardware output.

## Clean Evaluation

```bash
python -m benchmarks.run_eval \
  --data benchmarks/data/clean_dev.jsonl \
  --method hsc-rag-manual \
  --policy scoring/policy_manual.json \
  --profile-file profiles/paper_eval.yaml \
  --out build/eval/clean/manual_predictions.jsonl \
  --summary build/eval/clean/manual_summary.csv
```

## Robustness Evaluation

```bash
python -m benchmarks.run_eval \
  --data benchmarks/data/robustness_dev.jsonl \
  --method hsc-rag-de \
  --policy scoring/policy_de.json \
  --profile-file profiles/paper_eval.yaml \
  --out build/eval/robust/de_predictions.jsonl \
  --summary build/eval/robust/de_summary.csv
```

Each prediction row contains the benchmark case, reply, method, and full
orchestrator trace. The summary CSV and adjacent JSON contain route accuracy,
protocol hit rate, high-risk recall, unsafe response rate, latency, and related
paper metrics.
