# Results

## Main RAIR-RAG Test Results

本节报告 `benchmarks/rair_rag/data/test/rair_test.jsonl` 上的五种方法结果。表格应从 `build/rair_eval/rair_test_*_summary.json` 自动读取，不能混用 `artifacts/paper_final_v2/` 或 HSC-DisasterBench-v2 表格。

当前可引用的主结果：

| Method | RouteAcc | HRR | PFTR | NegRiskF1 | SecondaryIntentF1 |
|---|---:|---:|---:|---:|---:|
| keyword-baseline | 0.8000 | 0.8315 | 0.0083 | 0.0000 | 0.0000 |
| no-negation | 0.8208 | 0.9410 | 0.1542 | 0.0000 | 0.6533 |
| single-intent | 0.8083 | 0.8596 | 0.0021 | 0.7410 | 0.0000 |
| risk-router-manual | 0.9729 | 0.9831 | 0.0063 | 0.7410 | 0.8333 |
| risk-router-de | 0.9729 | 0.9831 | 0.0063 | 0.7410 | 0.8333 |

## Clean/Control Results

修正触发词覆盖和 clean/multi 主次意图口径后，`risk-router-manual` 在 test clean/control 子集上 RouteAcc 为 1.0000、HRR 为 1.0000、PFTR 为 0.0000。dev clean/control 子集同样达到 RouteAcc 1.0000。该结果用于回应 clean 子集稳定性问题；robust、negation 和 multi-intent 结果不再依赖 clean 漏词造成的模板偏差。

## Negation Conflict Results

本节只使用 `benchmarks/rair_rag/data/test/rair_test_negation.jsonl` 和 `build/rair_eval/rair_test_negation_*_summary.json`。重点报告 PFTR、NegRiskF1 和 RouteAcc。

当前结果显示，`no-negation` 在否定冲突子集上 PFTR 为 0.4868，而 `risk-router-manual` 降至 0.0197。这是 RAIR-RAG 的核心安全收益之一。

## Multi-Intent Results

本节只使用 `benchmarks/rair_rag/data/test/rair_test_multi_intent.jsonl` 和 `build/rair_eval/rair_test_multi_intent_*_summary.json`。重点报告 RouteAcc、HRR 和 SecondaryIntentF1。

当前 `risk-router-manual` 在 multi-intent 子集上 RouteAcc 为 0.9848，PFTR 为 0.0000，SecondaryIntentF1 为 0.8757。该结果用于支持“多意图输入应建模为风险优先级路由，而不是普通单标签分类”的论点。

## DE Calibration Effect

DE 只允许使用 dev split 进行 routing policy 参数校准。当前 `build/rair_eval/de_summary.json` 显示 `feasible_trial_found=true`，但 best policy 仍为 manual-baseline，因此论文中不能声称 DE 带来性能提升。

建议表述为：

> Differential Evolution was implemented as an offline calibration mechanism for routing parameters. In the current run, it identified a feasible policy, but the best policy remained the manual routing policy, so the DE result is reported as neutral rather than as a primary performance source.

## Legacy HSC Results

`artifacts/paper_final_v2/` 中的 final_v2 表格属于 HSC-RAG-DE / HSC-DisasterBench-v2 历史归档。它们不能与本章 RAIR-RAG-Bench 结果混表，也不能作为当前论文主结论来源。若需要引用，只能放在方法演进、历史基线或附录背景中，并明确标注为 legacy。
