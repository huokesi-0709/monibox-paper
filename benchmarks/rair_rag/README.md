# RAIR-RAG-Bench

RAIR-RAG-Bench is designed for evaluating pre-retrieval risk context construction in safety-critical RAG. It focuses on whether a system can identify positive risks, negated risks, primary intent, secondary intents, operational constraints, suppressed protocols, and predicted routes before retrieval and generation.

当前基准集用于离线灾害应急援助场景，不声称覆盖医疗、法律、金融等全部 safety-critical domains。它不是最终回答生成数据集，而是检验“检索前风险语义结构是否被正确构建”的基准集。

## Data Files

```text
data/gold/rair_gold_all.jsonl
data/dev/rair_dev.jsonl
data/test/rair_test.jsonl
data/test/rair_test_negation.jsonl
data/test/rair_test_multi_intent.jsonl
data/test/rair_test_multi_intent_negation.jsonl
```

## Core Fields

| Field | Meaning | Role in RAIR |
|---|---|---|
| `raw_input` | 原始输入 | 模拟受困者表达 |
| `canonical_input` | 归一化输入 | 便于标注和路由 |
| `risk_candidates` | 风险候选集合 | Step 1 |
| `positive_risks` | 正向风险 | Step 2 输出 |
| `negated_risks` | 被否定风险 | Step 2 输出 |
| `primary_intent` | 主意图 | Step 3 输出 |
| `secondary_intents` | 次级意图 | Step 3 输出 |
| `operational_constraints` | 操作约束 | Step 3 输出 |
| `suppressed_protocols` | 抑制协议 | Step 4 输出 |
| `expected_route` | 标准路由 | 评估 `RouteAcc` |
| `expected_protocol_id` | 标准协议 ID | 协议级评估 |
| `should_not_trigger` | 不应触发协议 | 兼容旧字段 |
| `risk_level` | 风险等级 | `HRR` 分析 |
| `guideline_refs` | 权威资料引用 | 数据来源说明 |

## evidence_type

| evidence_type | Definition | Example |
|---|---|---|
| `lexical` | 风险词表直接匹配 | “腿疼” |
| `protocol_alias` | 协议级风险表达 | “血止不住”“喘不上气” |
| `operational` | 设备或资源约束 | “手机快没电了” |
| `scene_context` | 灾害场景线索 | “废墟里”“门打不开” |
| `unknown` | 无法归类的兜底类型 | 边界样本 |

## evidence_source

| evidence_source | Definition |
|---|---|
| `risk_lexicon` | 来自风险词表 |
| `emergency_protocol_alias` | 来自应急协议别名 |
| `device_or_resource_constraint` | 来自设备、电量、通信或资源约束 |
| `disaster_scene_context` | 来自灾害场景线索 |
| `manual_boundary_case` | 人工构造边界样本 |

## Perturbation Types

| perturbation_type | Meaning |
|---|---|
| `clean_control` | 干净对照输入 |
| `negation_conflict` | 否定冲突输入 |
| `multi_intent` | 多意图输入 |
| `multi_intent_negation` | 多意图 + 否定冲突复合输入 |
| `out_of_scope` | 越界或无关输入 |
| `mixed_out_of_scope` | 灾害场景中夹杂无关请求 |

## Evaluation Metrics

- `RouteAcc`：预测路由是否与标准路由一致。
- `HRR`：高风险召回率。
- `PFTR`：协议误触发率，越低越好。
- `NegRiskF1`：被否定风险识别 F1。
- `SecondaryIntentF1`：次级意图保留 F1。
- `ConstraintF1`：操作约束识别 F1。
- `SuppressedProtocolF1`：抑制协议识别 F1。
- `RiskCandidateF1`：风险候选抽取 F1。
- `EvidenceTypeAcc`：证据类型识别准确率。

## Reproducibility

```bash
bash scripts/run_rair_eval.sh
python experiments/export_rair_tables.py
```

## Scope Note

RAIR-RAG-Bench 聚焦于安全关键 RAG 的检索前风险上下文构建，不直接评估最终自然语言回答质量。它强调的是：系统是否能在检索前正确构建风险语义结构，而不是是否生成了一段看起来合理的回答。
