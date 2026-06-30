# RAIR-RAG-Bench

RAIR-RAG-Bench 用于评估 safety-critical RAG 中的检索前风险上下文构建。它关注系统能否在检索和生成之前识别并组织 `risk_candidates`、正向风险、被否定风险、主意图、次级意图、操作约束、抑制协议和预测路由。

该数据集不是最终回答生成数据集，也不评价自然语言回复质量。当前验证场景限定为离线灾害应急辅助，不声称覆盖医疗、法律、金融等全部 safety-critical domains。

## 数据文件

```text
data/gold/rair_gold_all.jsonl
data/dev/rair_dev.jsonl
data/test/rair_test.jsonl
data/test/rair_test_negation.jsonl
data/test/rair_test_multi_intent.jsonl
data/test/rair_test_multi_intent_negation.jsonl
```

## 标注状态

主测试集 `rair_test.jsonl` 中的样本使用 `label_status=consensus` 和 `source_type=template_generated_human_reviewed`，表示模板辅助构造后经过人工复核。

复合扰动扩展集 `rair_test_multi_intent_negation.jsonl` 使用 `label_status=template_composed_pending_review` 和 `source_type=template_composed_multi_intent_negation`。该子集用于压力测试“多意图 + 否定冲突”的复合场景；除非后续完成独立人工复核，否则论文中应描述为“模板组合构造的复合扰动扩展集”，不应称为全量人工 consensus 标注。

## 核心字段

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
| `guideline_refs` | 资料引用 | 数据来源说明 |
| `label_status` | 标注状态 | 区分 consensus 与扩展构造集 |
| `source_type` | 样本来源 | 描述模板生成、人工复核或组合构造 |

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

## 扰动类型

| perturbation_type | Meaning |
|---|---|
| `clean_control` | 干净对照输入 |
| `negation_conflict` | 否定冲突输入 |
| `multi_intent` | 多意图输入 |
| `multi_intent_negation` | 多意图 + 否定冲突复合输入 |
| `out_of_scope` | 越界或无关输入 |
| `mixed_out_of_scope` | 灾害场景中夹杂无关请求 |

## 评价指标

- `RouteAcc`：预测路由是否与标准路由一致。
- `HRR`：高风险召回率。
- `PFTR`：协议误触发率，越低越好。
- `NegRiskF1`：被否定风险识别 F1。
- `SecondaryIntentF1`：次级意图保留 F1。
- `ConstraintF1`：操作约束识别 F1。
- `SuppressedProtocolF1`：抑制协议识别 F1。
- `RiskCandidateF1`：风险候选抽取 F1。
- `EvidenceTypeAcc`：证据类型识别准确率。

## 复现

Linux/macOS 或 Git Bash：

```bash
bash scripts/run_rair_eval.sh
python -m experiments.export_rair_tables
```

Windows PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_rair_eval.ps1
python -m experiments.export_rair_tables
```

运行时延可通过以下命令重新测量：

```bash
uv run python -m benchmarks.rair_rag.scripts.build_runtime_latency_summary
```

时延结果是运行环境相关的辅助分析，不作为主准确率实验指标。

## 范围说明

RAIR-RAG-Bench 聚焦安全关键 RAG 的检索前风险上下文构建。RAG 检索和生成是 RAIR `risk_context` 的下游消费者，不是该基准优化或直接评价的组件。
