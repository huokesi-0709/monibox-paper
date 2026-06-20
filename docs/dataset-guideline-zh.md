# MoniBox / HSC-RAG-DE 评测数据集指南

本文档用于维护论文复现实验中的 `clean` 与 `robustness` JSONL 数据。

## 数据格式

每行是一个 JSON 对象，建议字段如下：

- `id`：样本唯一 ID。
- `clean_id` / `canonical_id`：鲁棒扰动样本对应的 clean 样本 ID。
- `query`：实际输入系统的文本。
- `clean_query`：无扰动、语义等价的规范输入。
- `perturbation_type`：扰动类型；clean 数据可填 `clean`。
- `risk_level`：`low`、`medium`、`high`。
- `expected_route`：期望主路由或最高风险意图。
- `expected_protocol_id`：期望协议 ID；否定冲突、域外或护栏样本可为空。
- `expected_primary_intent`：期望最高风险意图。
- `expected_tags`：期望标签。
- `gold_chunk_ids`：人工标注的证据 chunk ID，可先留空。
- `unsafe_actions`：回复中不应出现的危险动作或承诺。
- `reference_reply`：人工参考回复。

## 鲁棒扰动类型

- `asr_homophone`：ASR 错听，例如“喘不上气”变为“穿不上气”。
- `filler_noise`：口语噪声，例如“呃”“啊”“咳咳”“救命救命”。
- `repetition`：重复高风险词，例如“流血流血流血”。
- `long_context`：加入灾害背景、手机低电量、害怕等次要信息。
- `multi_intent`：合并多个 clean case，期望主意图应为最高风险意图。
- `negation_conflict`：显式否定高风险，例如“腿疼但是没流血”。
- `out_of_scope`：域外输入，期望系统澄清或回到应急求助。
- `unsafe_induction`：询问止血带、药物剂量、保证获救时间等护栏诱导。

## 人工复核规则

生成器只用于构造评测集初稿，论文报告前必须人工检查：

1. `query` 与 `clean_query` 是否语义一致，除非扰动类型本身是域外或安全诱导。
2. `expected_primary_intent` 是否符合风险优先级。
3. `negation_conflict` 不应保留被否定风险的协议 ID。
4. `unsafe_induction` 不应包含具体医学操作步骤或剂量，只用于测试护栏。
5. `unsafe_actions` 应覆盖该样本中禁止出现在回复里的危险词或承诺。
6. `gold_chunk_ids` 应在知识库稳定后由人工标注。

## 生成命令

```bash
python -m benchmarks.perturbation_builder \
  --input benchmarks/data/clean_dev.jsonl \
  --out benchmarks/data/robustness_dev.jsonl \
  --max_per_case 3 \
  --seed 42
```

生成后会写入 `build/eval/perturbation_report.json`，统计各扰动类型数量。
