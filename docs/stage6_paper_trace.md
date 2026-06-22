# 阶段 6 论文 Trace Schema 说明

阶段 6 的目标是把 MoniBox / HSC-RAG-DE 主链路中的关键中间结果串成可审计记录。paper trace 覆盖输入归一化、意图抽取、协议匹配、HSC-RAG 重排、低证据路由、安全 guard 和最终输出，用于论文实验复现、错误分析和表格导出。

trace 是实验解释工具，不是用户隐私日志。trace 应保持 JSON 可解析结构，不应扩展为自然语言运行日志，也不应额外收集与论文实验无关的隐私信息。

## trace_version

`trace_version` 默认是 `paper-trace-v1`。该字段用于标识论文实验 trace schema 版本，便于后续 metrics、ablation 和 table export 在字段扩展后仍能区分来源。

## 核心字段

`input_normalization` 记录输入归一化动作，包括 `changed`、corrections、噪声移除和重复折叠统计。它用于判断鲁棒性提升是否来自 ASR 纠错、口语噪声处理或重复呼救折叠。

`intent_context` 记录阶段 3 的风险感知多意图抽取结果，包括 primary intent、secondary intents、risk_score、negated_risks、matched_terms、body_parts 和 scene_terms。它用于解释协议匹配和 RAG 重排使用了哪些风险信号。

`protocol_match` 记录阶段 4 的协议匹配结果，包括 matched、confidence、reason、negation_conflict、score_breakdown 和 protocol risks。它用于分析协议命中、误触发、否定冲突和 none_of/exclude_words 阻断。

`top_chunks` 记录阶段 5 的 RAG 候选片段。每个 top chunk 包含 rank、chunk_id、source_id、category、sub_category、tags_flat、text_preview、distance、final_distance 和 score_breakdown。`text_preview` 只保留短预览，避免把过长全文塞进 trace。

`score_breakdown` 记录 HSC-RAG 重排因子，例如 sim_vec、sim_sparse、quality、tag_match、risk_match、unsafe、redundancy 和 explanation。它用于解释候选证据为什么被提升或降权。

`output_guard` 和 `guard_result` 记录安全 guard 与输出处理结果，用于分析 unsafe 建议、过度承诺或被 guard 改写/拦截的情况。

`latency_ms` 记录单轮处理耗时，用于后续离线实验报告的效率统计。

`reply` 记录最终输出文本，用于 metrics 和人工复核。论文实验中应避免把 trace 当作面向用户展示的日志。

`metadata` 记录实验元信息，例如 method、disabled_modules、profile、policy、ablation、suite 和 data_path。benchmark prediction 会保留 trace 及其 metadata，便于后续按方法、消融项和数据集切分。

## Benchmark Predictions

`benchmarks/run_eval.py` 在 session 预测时会把 `session.last_trace` 写入 prediction 的 `trace` 字段，并补充 method、disabled_modules、profile、policy、ablation、suite 或 data_path 等元信息。metrics 计算仍基于 prediction 和 case，不依赖真实运行日志。

## 后续阶段使用

阶段 7 metrics 可以从 trace/prediction 中读取 protocol_confidence、top_chunks、score_breakdown、guard_level、latency_ms 等字段，计算 evidence_hit@k、unsafe_response_rate、协议命中质量和耗时统计。

阶段 9 ablation 可以比较 `metadata.disabled_modules`，分析输入归一化、多意图抽取、协议 gate、安全重排、低证据路由和 guard 对实验结果的贡献。

阶段 11 表格导出可以汇总协议置信度、证据分数、安全拦截、低证据路由比例和耗时，并将结果导出到论文表格。
