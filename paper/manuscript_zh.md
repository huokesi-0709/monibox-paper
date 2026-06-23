# 面向灾害受困场景的鲁棒启发式安全约束离线 RAG 应急回复生成方法

## 摘要

灾害受困场景通常伴随通信中断、端侧算力受限、环境噪声强、输入不完整以及回复风险高等约束。开放式大语言模型虽然具备较强语言生成能力，但在断网和高风险应急条件下，可能受到远端服务不可用、证据不足、过度承诺和危险建议等问题影响。本文围绕受困人员文本求助这一受限任务，研究一种离线、确定性、低随机性的应急回复生成方法 HSC-RAG-DE。该方法采用离线 RAG 作为知识访问基础，并在生成前引入协议优先策略、风险感知多意图抽取、协议置信度匹配、HSC-RAG 启发式安全约束重排、低证据分流和输出安全 guard。对于重排中的权重系数，本文使用 pymoo 提供的差分进化方法进行离线搜索，以得到开发集上的权重配置；该步骤优化的是工程评分系数，不是训练新的语言模型或医学规则。实验工程链路包含 clean/robust/dev benchmark、鲁棒扰动生成器、baselines/ablations、paper trace 和结果导表。本文不声称提供医学诊断，不声称替代专业救援，也不声称保证救援结果；当前数据仍为 dev/smoke 数据，最终 SCI 实验需要扩展样本规模、补齐 gold evidence 并进行独立测试集验证。

## 关键词

灾害应急；离线 RAG；安全约束；多意图识别；鲁棒性评估；差分进化

## 1 引言

地震、坍塌、洪水等灾害现场中，受困人员可能只能通过简短、带噪声或断续的文本描述表达当前状态。此类场景对回复系统提出了与普通聊天系统不同的要求：系统需要在断网或弱网条件下工作，需要优先避免危险建议，需要在证据不足时克制回复，并需要将协议类安全处置建议置于开放式生成之前。

现有开放式生成模型在一般问答中表现较强，但如果直接用于灾害受困场景，可能出现若干风险。其一，远端模型依赖网络和服务稳定性，难以满足灾害现场离线运行需求。其二，开放式生成容易在证据不足时给出貌似确定的建议。其三，高风险输入中常见 ASR 错听、口语噪声、重复呼救、否定冲突和多意图混合，若缺乏鲁棒处理，可能导致错误路由或错误协议触发。

本文关注的问题不是构建完整软硬件救援产品，而是在论文主实验边界内研究一条离线、可解释、低随机性的应急回复生成链路。本文方法 HSC-RAG-DE 将输入归一化、风险感知意图抽取、协议优先匹配、RAG 候选证据检索、安全约束重排、低证据分流和输出 guard 组合为一个可复现实验系统。

本文的工程贡献包括：构建 paper profile 固定离线配置；实现输入归一化、意图抽取、协议匹配和 HSC-RAG 重排的结构化 trace；建立 clean/robust/dev benchmark schema 与 metrics；实现鲁棒扰动生成器；定义 baselines 和 ablations；使用 pymoo Differential Evolution 离线搜索重排权重；提供结果导表流程。上述贡献均限定在开发集复现实验范围内，不应被解释为真实灾害现场医学验证。

## 2 相关工作

RAG 与知识增强生成通过检索外部知识片段为生成过程提供证据基础，常用于降低模型幻觉和改善领域问答可靠性。[待补充引用] 在高风险场景中，RAG 的关键不只是检索相关文本，还包括如何处理证据不足、冲突证据和不适合执行的建议。

安全约束生成研究关注模型输出中的危险建议、过度承诺、诊断性断言和不受支持的结论。[待补充引用] 本文采用启发式安全约束和输出 guard，而不是把大语言模型自由生成能力作为主要贡献。

灾害与应急人机交互强调低资源、弱连接、用户压力高和输入不完整等条件。[待补充引用] 这类场景要求系统回复短、稳、可解释，并优先遵循应急协议边界。

鲁棒性评估与扰动测试用于检验系统面对噪声输入、长上下文、多意图和否定表达时是否稳定。[待补充引用] 本文通过 clean 到 robust 的 deterministic perturbation generator 固定扰动来源，使评估可复现。

差分进化是一类常见的工程参数优化方法，可用于黑盒目标下的连续变量搜索。[待补充引用] 本文使用 pymoo 中已有 Differential Evolution 实现搜索 HSC-RAG 权重，并不提出新的进化算法。

## 3 方法

### 3.1 系统总体流程

系统输入为用户原始文本。流程依次包括输入归一化、风险感知多意图抽取、协议匹配与置信度计算、协议优先回复或 RAG 检索、HSC-RAG 安全约束重排、低证据分流、输出 guard 和 paper trace 记录。主实验使用 `profiles/paper_eval.yaml`，默认关闭远端 LLM、TTS 和硬件路径。

### 3.2 输入归一化

阶段 2 的 input normalizer 位于 intent extraction、protocol matching 和 RAG search 之前。其作用是处理 Unicode/标点差异、ASR exact correction、上下文模糊纠错、口语噪声和重复呼救。该模块不做医学判断，不推断用户没有说出的症状，也不把否定表达改写成肯定风险。

### 3.3 风险感知多意图抽取

阶段 3 的 intent extractor 从 canonical text 中抽取 `IntentContext`，包括 primary intent、secondary intents、risk score、body parts、scene terms、tags、negated risks 和 matched terms。风险分数是启发式工程评分，不是临床分诊或真实救援严重程度预测。

### 3.4 协议优先匹配与置信度

阶段 4 的 protocol matcher 在意图抽取之后运行，输入包括 canonical text、routed tags、events 和 IntentContext。输出为 `ProtocolMatchResult`。confidence 是启发式工程评分，不是概率，也不是医学判断。否定冲突用于阻断“没流血”“不是被困”等表达误触发高风险协议。

### 3.5 HSC-RAG 安全约束重排

阶段 5 的 HSC-RAG rerank 对候选知识片段进行重排。评分因子包括 `sim_vec`、`sim_sparse`、`quality`、`tag_match`、`risk_match`、`unsafe` 和 `redundancy`。该过程是启发式工程评分，不是训练模型，也不是医学诊断。manual policy 使用人工权重；DE policy 使用离线搜索得到的权重系数。

### 3.6 低证据分流

当检索证据不足或候选质量低时，系统进入低证据分流路径，避免在证据不足时给出过度确定的处置建议。该策略强调克制回复、澄清需求和安全边界。

### 3.7 输出安全 guard

输出 guard 用于检测危险建议、过度承诺、药物剂量、诊断性断言等风险。guard 不能证明系统医学安全，只是论文工程链路中的一层安全约束。

### 3.8 DE 权重优化

阶段 10 使用 pymoo 的 Differential Evolution 对 HSC-RAG scoring coefficients 进行离线搜索。搜索空间来自 `scoring/search_space.json`，输出 policy 记录 optimizer、seed、n_eval、best_fitness 和 dev_datasets。DE 只使用 dev 数据，不使用 final test set 调参。

### 3.9 Paper trace

阶段 6 的 paper trace 将输入归一化、意图抽取、协议匹配、HSC-RAG 重排、低证据决策、guard 和输出串成 JSON 结构。trace 用于实验解释、错误分析和导表，不是用户隐私日志。

## 4 实验设置

主实验使用 `profiles/paper_eval.yaml`。该 profile 显式关闭远端 LLM、rewrite、TTS 和硬件接口，设置低随机性和 runtime trace，用于论文复现实验。

当前数据包括 `benchmarks/data/clean_dev.jsonl` 与 `benchmarks/data/robustness_dev.jsonl`。前者用于 clean evaluation，后者由鲁棒扰动生成器或人工维护样例构成，用于 robust evaluation。二者仍是 dev/smoke 数据，不等同最终 SCI test set。

benchmark schema 由阶段 7 固定，字段包括 `id`、`query`、`risk_level`、`expected_route`、`expected_protocol_id`、`expected_primary_intent`、`expected_tags`、`gold_chunk_ids`、`unsafe_actions` 和 `reference_reply`。其中 `gold_chunk_ids` 是证据评价的重要字段；若为空，evidence_hit 指标不可过度解释。

metrics 包括 route accuracy、protocol hit rate、high-risk recall/miss rate、evidence hit、unsafe response rate、unsupported claim rate、primary intent accuracy、protocol false trigger rate、robust consistency 和 latency。summary 中同时导出 `num_*` 分母字段。

对照方法包括 baseline、rule-only、vanilla-rag、rag-guard、hsc-rag-manual 和 hsc-rag-de。baseline 与 rule-only 使用 expected label 生成模板回复，属于 oracle-label deterministic template/smoke baseline，不是公平真实模型 baseline。

消融包括 without_input_normalization、without_multi_intent、without_negation、without_protocol_gate、without_safety_rerank、without_low_evidence、without_guard 和 without_de_optimization。其中 without_multi_intent 实际关闭 risk-aware intent extraction；without_safety_rerank 使用 vector-only policy；without_de_optimization 使用 manual policy。

DE 配置位于 `experiments/configs/de_hsc_rag.yaml`。结果导出由阶段 11 的 `experiments/export_tables.py` 完成，输出 CSV 与 Markdown 表格。所有实验结果均应从 `build/eval` 及导出表格读取。

## 5 实验结果

本节不手写实验数值。所有结果应由阶段 11 导出的表格填入。

表 1 展示 clean evaluation 主结果，结果由 `build/eval/main_results.csv` 导出。

表 2 展示 robust evaluation 结果，结果由 `build/eval/robustness_results.csv` 导出。

表 3 展示 ablation 结果，结果由 `build/eval/ablation_results.csv` 导出。

表 4 展示 DE 权重搜索效果，结果由 `build/eval/de_effect_results.csv` 导出。

表 5 展示 trace audit 结果，结果由 `build/eval/trace_audit_results.csv` 导出。

报告上述表格时必须同时说明数据仍为 dev/smoke，并报告关键 count 分母，尤其是 `num_evidence_eval_cases`。

## 6 讨论

协议优先策略的意义在于，当输入明确匹配应急协议时，系统可以优先返回受约束的处置建议，而不是直接进入开放式生成路径。这有助于降低高风险建议的不确定性。

安全约束重排使 RAG 不仅关注向量相似度，也考虑风险标签、身体部位、场景词、片段质量、unsafe pattern 和冗余。该设计有利于把更适合应急回复的片段排在前列。

低证据分流是高风险场景中的必要保护。当证据不足时，系统不应为了完整回答而补全不确定内容，而应倾向于安全澄清和保守回复。

鲁棒扰动生成器使 ASR 错听、口语噪声、重复呼救、长上下文、多意图和否定冲突能够被系统性测试。它并不替代最终真实数据评估，但能提高开发阶段错误发现能力。

离线边缘场景仍存在工程限制，包括设备算力、存储、语音链路稳定性、电源、传感器和长期部署可靠性。本文主实验仅评估离线文本链路，不声称完整硬件部署已经完成。

## 7 局限性

当前数据集是 dev/smoke 数据，样本规模和覆盖范围不足以支持最终 SCI 结论。

当 `gold_chunk_ids` 标注不足或为空时，evidence_hit 指标不能被解释为完整 RAG 证据能力。

本文方法不提供医学诊断，不替代专业救援，也不保证救援结果。

真实灾害现场仍需要硬件、通信、语音、功耗、用户交互和伦理安全验证。

DE 权重仅在开发集上优化，不应在 final test set 上调参。若后续建立最终测试集，应冻结 policy 后再进行一次性报告。

## 8 结论

本文提出并工程化实现了一条面向灾害受困文本求助场景的离线 HSC-RAG-DE 应急回复生成链路。该链路通过输入归一化、风险感知多意图抽取、协议优先匹配、安全约束重排、低证据分流、输出 guard 和 paper trace，提高了开发集复现实验中的可解释性和可检查性。本文贡献主要在论文工程基线、方法边界、鲁棒评估和离线权重优化流程，不应被解读为真实灾害现场医学验证或救援保证。
