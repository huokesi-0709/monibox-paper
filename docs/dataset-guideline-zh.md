# 数据集标注指南

本文档用于维护 HSC-RAG-DE 论文复现实验中的 clean 与 robustness JSONL 数据。

## JSONL 字段

每行是一个 JSON object，推荐字段如下：

- `id`：样本唯一 ID。
- `clean_id` / `canonical_id`：鲁棒扰动样本对应的 clean 样本 ID。
- `query`：实际输入系统的文本。
- `clean_query`：语义等价的规范输入；域外和安全诱导样本可为空。
- `perturbation_type`：扰动类型；clean 数据可为 `clean`。
- `risk_level`：`low`、`medium`、`high` 或 `critical`。
- `expected_route`：期望主路由或最高风险意图。
- `expected_protocol_id`：期望协议 ID；否定冲突、域外或护栏样本可为空。
- `expected_primary_intent`：期望最高风险意图。
- `expected_tags`：期望标签列表。
- `gold_chunk_ids`：人工标注证据 chunk ID，可在知识库稳定后补齐。
- `unsafe_actions`：回复中不应出现的危险动作、诊断或承诺。
- `reference_reply`：人工参考回复，可为空。

## 鲁棒性场景矩阵

| 编号 | perturbation_type | 目标 |
| --- | --- | --- |
| R0 | clean | 干净短句，验证基础 route/protocol/evidence。 |
| R1 | asr_homophone | ASR 错听，如“留血”“穿不上气”“旧我”。 |
| R2 | filler_noise | 口语噪声，如“呃”“啊”“咳咳”“救命救命”。 |
| R3 | repetition | 重复词或重复短句，如“喘不上气喘不上气”。 |
| R4 | long_context | 灾害背景、手机低电量、害怕等长上下文。 |
| R5 | multi_intent | 多风险混合，要求选择最高风险 primary intent。 |
| R6 | negation_conflict | 否定冲突，如“腿疼但是没流血”，不得误触发被否定协议。 |
| R7 | out_of_scope | 域外输入，期望 fallback 或澄清。 |
| R8 | unsafe_induction | 危险诱导，如询问止血带、药物剂量、保证获救时间。 |

## 人工复核规则

1. `query` 与 `clean_query` 应语义一致，除非样本是域外或安全诱导。
2. `expected_primary_intent` 必须符合风险优先级。
3. `negation_conflict` 不应保留被否定风险的 `expected_protocol_id`。
4. `unsafe_induction` 不能包含可执行的危险医学步骤或剂量。
5. `unsafe_actions` 应覆盖回复中禁止出现的危险词或承诺。
6. `gold_chunk_ids` 应在知识库稳定后由人工标注。

## 生成命令

```bash
python -m benchmarks.perturbation_builder \
  --input benchmarks/data/clean_dev.jsonl \
  --out benchmarks/data/robustness_dev.jsonl \
  --max_per_case 3 \
  --seed 42
```

生成后会写入 `build/eval/perturbation_report.json`。正式论文报告前必须人工检查生成样本。
