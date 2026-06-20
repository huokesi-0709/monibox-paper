# MoniBox / HSC-RAG-DE 实验协议

本文档说明论文 benchmark 中 baseline 与 ablation 的运行方式。所有对比实验都通过
`benchmarks.run_eval` 的配置注入完成，不通过手动修改源代码完成。

## 主方法与 Baseline

- `rule-only`：规则回复基线，不走 RAG 生成。
- `vanilla-rag`：关闭输入归一化、意图抽取、协议门、安全重排、低证据路由和安全护栏。
- `rag-guard`：在 `vanilla-rag` 基础上打开安全护栏。
- `hsc-rag-manual`：完整 HSC-RAG，使用 `scoring/policy_manual.json`。
- `hsc-rag-de`：完整 HSC-RAG-DE，使用 `scoring/policy_de.json`。

## 消融项

- `without_input_normalization`：关闭 ASR/口语输入归一化。
- `without_multi_intent`：关闭多意图抽取，主意图退化为低风险域外占位。
- `without_negation`：保留意图抽取，但清空否定风险信息。
- `without_protocol_gate`：协议门永不命中。
- `without_safety_rerank`：使用 vector-only policy，关闭风险、标签、unsafe、冗余等安全重排项。
- `without_low_evidence`：关闭低证据路由。
- `without_guard`：安全护栏改为 pass-through。
- `without_de_optimization`：使用 manual policy 代替 DE policy。

## 运行示例

```bash
python -m benchmarks.run_eval \
  --data benchmarks/data/clean_dev.jsonl \
  --method vanilla-rag \
  --profile-file profiles/paper_eval.yaml \
  --output-dir build/eval/main
```

```bash
python -m benchmarks.run_eval \
  --data benchmarks/data/robustness_dev.jsonl \
  --method hsc-rag-de \
  --ablation without_input_normalization \
  --profile-file profiles/paper_eval.yaml \
  --output-dir build/eval/ablation
```

每条 prediction 的 trace metadata 会记录：

- `method`
- `disabled_modules`

主结果写入 `main_results.csv`，消融结果写入 `ablation_results.csv`。
