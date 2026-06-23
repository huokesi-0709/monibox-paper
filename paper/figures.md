# 论文图清单

本文件列出建议绘制的论文图。若仓库中没有对应图像文件，本文只保留图的设计说明，不编造图片路径。

## Figure 1: 系统整体流程图

建议内容：输入归一化 → 风险感知多意图抽取 → 协议匹配与置信度 → HSC-RAG 检索与安全约束重排 → 低证据分流 → 输出 guard → 应急回复。

对应章节：第 3.1 节系统总体流程。

已有资源：可参考 `docs/images/monibox-system-overview.png`（如果该文件存在）。若不存在，后续应重新绘制。

## Figure 2: HSC-RAG 安全约束重排流程

建议内容：candidate chunks、routed tags、IntentContext、HscRagPolicy 输入；展示 `sim_vec`、`sim_sparse`、`quality`、`tag_match`、`risk_match`、`unsafe`、`redundancy` 如何形成 score breakdown 和最终排序。

对应章节：第 3.5 节 HSC-RAG 安全约束重排。

已有资源：暂无固定图片文件。

## Figure 3: benchmark 与 trace 评估流程

建议内容：clean/robust JSONL → run_eval → predictions JSONL → summary CSV/JSON → export_tables → paper tables；同时标出 paper trace 中 input_normalization、intent_context、protocol_match、top_chunks、guard 和 metadata。

对应章节：第 4 节实验设置和第 5 节实验结果。

已有资源：暂无固定图片文件。

## Figure 4: DE 权重优化流程

建议内容：search_space.json → candidate policy → clean/robust dev evaluation → fitness/constraints → pymoo Differential Evolution → policy_de.json。

对应章节：第 3.8 节和第 4 节 DE config。

已有资源：暂无固定图片文件。

## Figure 5: 鲁棒性扰动生成流程

建议内容：clean_dev.jsonl → deterministic perturbation generator → asr_homophone、filler_noise、repetition、long_context、multi_intent、negation_conflict、out_of_scope、unsafe_induction → robustness_dev.jsonl。

对应章节：第 4 节 robust benchmark 设置和第 6 节鲁棒扰动讨论。

已有资源：暂无固定图片文件。
