# Legacy HSC-RAG paper final_v2 experiment package

> Legacy notice: this package belongs to the old HSC-RAG-DE / HSC-DisasterBench-v2 line. It is not the current RAIR-RAG-Bench paper evidence package. Current RAIR-RAG paper results should come from `benchmarks/rair_rag/` and `build/rair_eval/`.

This directory contains the reproducible experiment package for the HSC-RAG paper.

本目录包含 HSC-RAG 论文 final_v2 历史实验包。旧结果来自 HSC-DisasterBench-v2 的全量 test 评测。数字复核材料仅用于辅助误差分析，不作为真实应急医学或救援专家评估。

当前 RAIR-RAG 论文主线不得把本目录中的表格、统计和 validation report 混入 RAIR-RAG-Bench 主表。若引用本目录，只能作为 legacy baseline、历史归档或方法演进背景，并必须显式标注 HSC-RAG-DE / HSC-DisasterBench-v2。

## Contents

- `dataset/`: dataset card, audit report, and split manifest.
- `summaries/`: final_v2 summary JSON files for clean, robust, ablation, and DE multiseed runs.
- `tables/`: paper-ready markdown and CSV tables.
- `statistics/`: exported metrics, bootstrap CI, warnings, and statistics reports.
- `cases/`: selected real prediction cases for error analysis.
- `human_review/`: balanced digital review sample, A/B/C labels, and disagreement report.
- `manifests/`: final run and paper evidence manifests.
- `validation/`: final_v2 validation reports.
- `predictions_manifest.md`: prediction file paths, sample counts, and hashes. Prediction JSONL files are kept in `build/eval/final_v2/` and are not duplicated here.

## Rule

For the legacy HSC paper line, conclusions should be based on full test automatic metrics. Digital review artifacts are auxiliary error-analysis evidence only.

For the current RAIR-RAG paper line, do not use this directory as the primary result source. Use:

```text
benchmarks/rair_rag/
build/rair_eval/
```
