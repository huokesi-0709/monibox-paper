# final_v2 论文第 4 章回填指南

> Legacy notice: this guide is only for the old HSC-RAG-DE / HSC-DisasterBench-v2 paper line. It must not be used to fill the current RAIR-RAG paper main result tables. Current RAIR-RAG tables should be derived from `benchmarks/rair_rag/` and `build/rair_eval/`.


本指南用于约束 HSC-RAG 论文第 4 章的结果回填。所有主实验数字只能来自 `build/eval/final_v2/`，数据集说明来自 `benchmarks/data_v2/`，不要手工改写或混入 dev 调参结果。

## 1. 回填总原则

- 论文主结果使用 HSC-DisasterBench-v2 的 test split。
- dev split 只用于 DE 权重优化、阈值调整和规则调试，不能冒充 test 结果。
- 表格中的数字优先从 `build/eval/final_v2/tables/paper_tables_all.md` 复制。
- 单表复核时使用对应的 `table*.md` 或 `table*.csv`。
- 数字复核是辅助误差分析，不是专家人工评估。
- 除非 bootstrap CI 或统计检验明确支持，不写“显著提升”。

## 2. 数据集描述

数据集规模、split、类别分布、风险分布和泄漏检查引用：

- `benchmarks/data_v2/dataset_audit.md`
- `benchmarks/data_v2/dataset_card.md`
- `benchmarks/data_v2/split_manifest.json`
- `build/eval/final_v2/tables/table_dataset_distribution.md`

建议写法：

> 本文构建 HSC-DisasterBench-v2，共 6000 条样本，包括 1500 条 canonical clean 样本及其三类 robust 变体。dev/test 按 canonical_id 分组切分，避免同一 canonical 样本在调参与最终测试间泄漏。

## 3. 表格来源

| 论文位置 | 文件 |
| --- | --- |
| 数据集表 | `benchmarks/data_v2/dataset_audit.md` 和 `build/eval/final_v2/tables/table_dataset_distribution.md` |
| 表 11 整体性能 | `build/eval/final_v2/tables/table11_overall_performance.md` |
| 表 12 扰动类型分析 | `build/eval/final_v2/tables/table12_perturbation_results.md` |
| 表 13 消融实验 | `build/eval/final_v2/tables/table13_ablation_results.md` |
| 表 14 DE 效果 | `build/eval/final_v2/tables/table14_de_effect.md` |
| 表 15 安全性指标 | `build/eval/final_v2/tables/table15_safety_metrics.md` |
| 表 16 效率指标 | `build/eval/final_v2/tables/table16_efficiency.md` |
| 表 17 Bootstrap 95% CI | `build/eval/final_v2/tables/table17_bootstrap_ci.md` |
| 表 18 数字复核 | `build/eval/final_v2/tables/table18_digital_review.md` |
| 所有表格合集 | `build/eval/final_v2/tables/paper_tables_all.md` |

## 4. 案例分析来源

案例分析引用：

- `build/eval/final_v2/cases/selected_cases.md`
- `build/eval/final_v2/cases/selected_cases.json`

案例覆盖 severe bleeding、respiratory distress、crush trapped、negation conflict、unsafe request、low evidence 和 multi-intent 等场景。论文中应保留 case_id，方便从仓库追溯到原始 prediction。

## 5. 数字复核写法

数字复核引用：

- `build/eval/final_v2/human_review/review_sample_balanced_300.jsonl`
- `build/eval/final_v2/human_review/final_labels_C_balanced_300.jsonl`
- `build/eval/final_v2/human_review/disagreement_report_balanced_300.md`
- `build/eval/final_v2/tables/table18_digital_review.md`

建议写法：

> 为辅助分析自动指标难以覆盖的输出质量差异，本文进一步构建 balanced 数字复核样本，由三角色数字评测流程分别从应急安全、系统输出一致性和分歧裁决角度进行复核。该流程用于误差分析和案例归因，不作为真实应急医学或救援专家评估的替代。

不要写成：

- “专家人工评估”
- “临床专家确认”
- “救援专家复核”

## 6. 结果解释边界

如果 HSC-RAG-DE 没有明显优于 manual，建议写：

> DE 校准在 clean 输入下提升有限，但在 robust 输入和安全约束指标上表现出更稳定的趋势。

如果 Vanilla-RAG 某些指标也不错，建议写：

> 部分低风险或信息充分样本中，Vanilla-RAG 也能生成可接受回复，但在高风险、多意图和扰动输入下更容易出现路径偏移。

如果某些消融项下降不明显，建议写：

> 该模块在当前数据集上的单独影响有限，可能与测试样本中相关场景比例及规则重叠有关。

## 7. 局限性建议

局限性应至少覆盖：

- HSC-DisasterBench-v2 是构造化 benchmark，不等同真实灾害语音场景。
- robust 变体覆盖 filler noise、long context 和 repetition，但未覆盖真实 ASR 错字、方言、多人混杂说话等复杂噪声。
- 数字复核用于辅助误差分析，不替代真实应急医学或救援专家评估。
- 系统面向离线安全约束 RAG，不声称提供通用急救专家系统能力。
- 输出建议不能替代现场专业救援或医疗判断。

## 8. 验收文件

回填前先运行：

```bash
python -m experiments.validate_final_v2_evidence
```

验收报告：

- `build/eval/final_v2/final_v2_validation_report.md`
- `build/eval/final_v2/final_v2_validation_report.json`

只有关键文件齐全、无 dev/test 泄漏、表 11 到表 18 均生成、balanced 数字复核完成后，才开始回填论文第 4 章。
