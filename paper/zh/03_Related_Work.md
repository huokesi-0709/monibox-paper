# Related Work

## Retrieval-Augmented Generation

本节讨论 RAG 在开放域问答、垂直知识库和受限知识源场景中的应用，并指出普通 RAG 在灾害受困场景下的不足：证据不足、风险意图弱建模和安全约束不足。

## Safety-Constrained Generation

本节讨论安全回复生成、拒答策略、输出过滤和高风险建议约束。本文关注的是离线、低算力、规则可解释条件下的安全约束，而不是依赖在线大模型的 safety classifier。

## Emergency and Disaster Communication

本节讨论灾害场景中信息需求、受困者通信限制、情绪压力和高风险求助优先级。本文不替代专业救援流程，而是研究边缘设备上的应急回复辅助。

## Robustness under Imperfect Inputs

本节讨论 ASR 错听、口语噪声、重复输入、长上下文、多意图和否定冲突。本文将这些扰动纳入 benchmark，而不是只在干净短句上评估。

## Black-Box Optimization for System Calibration

本节讨论差分进化等黑盒优化方法在权重校准中的使用。本文使用 pymoo DE 作为离线工具，不将其作为核心算法贡献。
