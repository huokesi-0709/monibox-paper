# 阶段 9：baselines 与 ablations

> [!WARNING]
> OBSOLETE / HISTORICAL: This document is retained only as project history. Do not use it as the current RAIR-RAG paper or reproduction source. Current canonical entry points are `docs/RAIR_RAG_routing_reproduction.md`, `docs/RAIR_RAG_downstream_reproduction.md`, `models/README.md`, and `models/llm/README.md`.

阶段 9 的目标是定义论文实验中的主方法、对照方法和模块消融，使 clean/robust/dev 评估能够复现并解释。该阶段只固定 benchmark 配置和输出语义，不改变 runtime 主链路，不修改 metrics，也不引入远端 LLM。

## 方法定义

`baseline`：确定性 smoke baseline。当前实现通过 `baseline_reply(case)` 使用 `expected_primary_intent` 生成模板回复，因此属于 oracle-label deterministic template，不是公平真实系统 baseline。

`rule-only`：规则模板对照路径。当前配置与 `baseline` 基本一致，也使用 benchmark expected label。它可用于链路 smoke 和模板上界参考，不应作为主论文中与 HSC-RAG-DE 公平比较的核心模型 baseline。

`vanilla-rag`：关闭输入归一化、风险感知意图抽取、否定处理、协议门控、安全重排、低证据分流和安全 guard 的简化 RAG 对照。

`rag-guard`：在 `vanilla-rag` 基础上只保留 safety guard，用于观察输出安全 guard 的独立影响。

`hsc-rag-manual`：启用 HSC-RAG 主链路，但使用人工设定的 `scoring/policy_manual.json`。该方法关闭 DE 权重优化。

`hsc-rag-de`：论文主方法。启用输入归一化、风险感知意图抽取、否定处理、协议门控、安全重排、低证据分流和安全 guard，并使用 `scoring/policy_de.json`。

## baseline 边界

`baseline` 和 `rule-only` 使用样本中的 expected label 生成 deterministic reply。这种设计适合验证 run_eval、trace、summary、metrics 和导表链路是否工作，但它不是一个部署时可用的无监督 baseline。

报告实验结果时，应明确说明这两类方法是 oracle-label template/smoke baseline。不要把它们描述为公平的真实模型 baseline，也不要据此推断开放式生成能力。

## 消融定义

`without_input_normalization`：关闭输入归一化，用于评估 ASR 错听、口语噪声、重复呼救等扰动的影响。

`without_multi_intent`：关闭整个 risk-aware intent extraction。该名称保留历史兼容性，但实际语义不是仅关闭 secondary intents，而是强消融意图抽取阶段。

`without_negation`：保留意图抽取，但移除否定风险处理，用于观察“没流血”“不是被困”等样本的误触发风险。

`without_protocol_gate`：关闭协议门控，使样本更多进入 RAG/生成路径，用于评估协议优先策略的贡献。

`without_safety_rerank`：关闭 HSC-RAG 安全重排。`run_eval._create_session()` 会将该配置映射到 `VECTOR_ONLY_POLICY`，即只按向量相似度排序。

`without_low_evidence`：关闭低证据分流，用于评估低证据场景下的安全回复边界。

`without_guard`：关闭输出 safety guard，用于观察危险建议、过度承诺和 unsupported claim 的变化。

`without_de_optimization`：保留 HSC-RAG 重排结构，但使用 `scoring/policy_manual.json`，用于比较 DE 搜索权重与人工权重。

## 脚本入口

clean evaluation：

```bash
scripts/run_clean_eval.sh
```

robust evaluation：

```bash
scripts/run_robust_eval.sh
```

ablation evaluation：

```bash
scripts/run_ablation.sh
```

这些脚本应使用 `profiles/paper_eval.yaml`。该 profile 默认关闭远端 LLM、语音和硬件路径，以保证论文复现实验不受本地 demo 配置影响。

## 输出产物

`benchmarks/run_eval.py` 输出：

- predictions JSONL：逐样本预测和 trace。
- summary CSV/JSON：单次运行指标摘要。
- `main_results.csv/json`：主方法和对照方法汇总。
- `ablation_results.csv/json`：消融实验汇总。

prediction trace 的 metadata 应包含 `method`、`disabled_modules`、`profile`、`policy`、`ablation`、`data_path` 和 `suite`，便于阶段 11 导表。

## 数据边界

当前 `clean_dev.jsonl` 与 `robustness_dev.jsonl` 是 dev/smoke 数据，用于验证实验链路和方法差异，不等同最终论文 test set。最终 SCI 实验仍需要扩展数据规模、补齐 gold evidence，并进行独立验证或测试划分。

## 后续阶段

阶段 10 的 DE 权重优化可以使用开发集 metrics 作为目标，但不应使用最终 test set 调参。

阶段 11 应从 `main_results.csv/json`、`ablation_results.csv/json` 和 predictions trace 中导出表格，并同时报告指标值和对应分母计数。
