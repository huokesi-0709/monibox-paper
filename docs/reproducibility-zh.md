# MoniBox / HSC-RAG-DE 复现实验说明

本文档记录论文实验的可复现运行约定。HSC-RAG 是主方法，pymoo Differential Evolution 只用于离线校准 `scoring/policy_de.json` 权重，部署和正式评测时不在线运行 DE。

## 基础约定

- 默认实验 profile 使用 `profiles/paper_eval.yaml`。
- 默认 LLM backend 为 `null`，不调用远端 API。
- clean、robustness、ablation、DE 优化结果统一写入 `build/eval/`。
- `build/eval/` 下的 CSV、JSONL、summary JSON 是可再生成产物，不应手工改数字。

## 运行评测

clean dev：

```bash
python -m benchmarks.run_eval --suite clean --method hsc-rag-de --policy scoring/policy_de.json --profile-file profiles/paper_eval.yaml --output-dir build/eval/clean
```

robustness dev：

```bash
python -m benchmarks.run_eval --suite robust --method hsc-rag-de --policy scoring/policy_de.json --profile-file profiles/paper_eval.yaml --output-dir build/eval/robust
```

ablation：

```bash
bash scripts/run_ablation.sh
```

DE 离线权重优化：

```bash
python -m experiments.de_pymoo_optimize --config experiments/configs/de_hsc_rag.yaml
```

## 导出论文表格

运行：

```bash
python -m experiments.export_tables --eval-dir build/eval --out-dir build/eval/tables
```

或：

```bash
bash scripts/export_tables.sh
```

导出器会从 `build/eval/` 递归读取各类 `*_summary.json` 和 `*_summary.csv`，并生成：

- `build/eval/main_results.csv`
- `build/eval/robustness_results.csv`
- `build/eval/ablation_results.csv`
- `build/eval/de_effect_results.csv`
- `build/eval/latency_memory_results.csv`
- `build/eval/tables/main_results.md`
- `build/eval/tables/robustness_results.md`
- `build/eval/tables/ablation_results.md`
- `build/eval/tables/de_effect_results.md`

如果缺少某类评测结果，导出器会打印 `[export_tables][WARN]`，并继续生成已有表格。论文表格中的数字应复制这些导出文件，不能手工统计或手工改写。

## 成功现象

- `uv run pytest` 通过。
- `python -m experiments.export_tables --eval-dir build/eval --out-dir build/eval/tables` 正常结束。
- `build/eval/*.csv` 和 `build/eval/tables/*.md` 被刷新。
- Markdown 表格中的 `method`、`route_accuracy`、`high_risk_recall`、`unsafe_response_rate` 等字段和对应 summary 文件一致。
