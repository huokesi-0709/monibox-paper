# 复现实验说明

本文档记录 MoniBox / HSC-RAG-DE 论文实验的可复现运行方式。HSC-RAG 是主方法；pymoo Differential Evolution 只用于离线校准 `scoring/policy_de.json` 权重；MoniBox 是 prototype validation platform。

## 安装依赖

基础开发依赖：

```bash
uv sync --group dev
```

论文实验依赖：

```bash
uv sync --extra paper --group dev
```

默认实验 profile 为 `profiles/paper_eval.yaml`，其中 LLM backend 为 `null`，不调用远端 API。

## 构建 RAG DB

```bash
uv run python -m devtools.build_rag
```

如果本地 embedding 模型缺失，系统可能 fallback 到 hash embedding。工程链路仍可跑通，但正式论文实验应补齐本地 embedding 模型并记录模型版本。

## Clean Eval

```bash
uv run python -m benchmarks.run_eval \
  --suite clean \
  --method hsc-rag-de \
  --policy scoring/policy_de.json \
  --profile-file profiles/paper_eval.yaml \
  --output-dir build/eval/clean
```

## Robust Eval

```bash
uv run python -m benchmarks.run_eval \
  --suite robust \
  --method hsc-rag-de \
  --policy scoring/policy_de.json \
  --profile-file profiles/paper_eval.yaml \
  --output-dir build/eval/robust
```

## DE 离线权重优化

```bash
uv run python -m experiments.de_pymoo_optimize \
  --config experiments/configs/de_hsc_rag.yaml
```

DE 只允许使用 dev 数据。不要把 test set 写入 `experiments/configs/de_hsc_rag.yaml`。

## Ablation

```bash
bash scripts/run_ablation.sh
```

或单独运行：

```bash
uv run python -m benchmarks.run_eval \
  --suite clean \
  --method hsc-rag-de \
  --ablation without_input_normalization \
  --profile-file profiles/paper_eval.yaml \
  --output-dir build/eval/ablation
```

## 导出论文表格

```bash
uv run python -m experiments.export_tables \
  --eval-dir build/eval \
  --out-dir build/eval/tables
```

或：

```bash
bash scripts/export_tables.sh
```

导出结果包括：

- `build/eval/main_results.csv`
- `build/eval/robustness_results.csv`
- `build/eval/ablation_results.csv`
- `build/eval/de_effect_results.csv`
- `build/eval/latency_memory_results.csv`
- `build/eval/tables/*.md`

论文表格数字应从这些文件复制，不要手工统计或手工改写。

## 验证

```bash
uv run pytest
```

成功现象：所有测试通过；eval 命令生成 predictions 与 summary；export_tables 生成 CSV 和 Markdown 表格，且没有未解释的 warning。
