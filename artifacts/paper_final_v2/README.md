# HSC-RAG paper final_v2 experiment package

This directory contains the reproducible experiment package for the HSC-RAG paper.

本目录包含 HSC-RAG 论文 final_v2 实验包。论文主结果来自 HSC-DisasterBench-v2 的全量 test 评测。数字复核材料仅用于辅助误差分析，不作为真实应急医学或救援专家评估。

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

The main paper conclusions should be based on full test automatic metrics. Digital review artifacts are auxiliary error-analysis evidence only.
