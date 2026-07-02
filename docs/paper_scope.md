# 论文研究边界说明

> [!WARNING]
> OBSOLETE / HISTORICAL: This document is retained only as project history. Do not use it as the current RAIR-RAG paper or reproduction source. Current canonical entry points are `docs/RAIR_RAG_routing_reproduction.md`, `docs/RAIR_RAG_downstream_reproduction.md`, `models/README.md`, and `models/llm/README.md`.

本文档用于说明 MoniBox / HSC-RAG-DE 仓库中与论文主实验相关的工程边界。其目的不是描述完整产品形态，而是帮助审稿人和复现实验者区分论文方法、离线实验入口、系统原型模块和当前不作声称的内容。

## 研究对象

本文研究对象是 HSC-RAG-DE 这条离线、确定性、低随机性的应急回复生成链路。该链路面向灾害受困场景中的文本化输入，优先使用本地知识库、协议规则、安全约束和可复现的评分/重排策略生成应急回复。

因此，当前论文研究的重点不是完整软硬件产品，也不是开放域聊天系统。仓库中存在 API demo、React frontend、语音链路和硬件预留代码，这些内容用于原型验证、演示、联调或未来部署探索，不构成当前论文主实验的评价对象。

## 论文主实验范围

论文主实验只评估以下离线实验链路：

- clean evaluation：在标准开发/评估样例上评估 HSC-RAG-DE 的回复质量、安全性和协议一致性。
- robust evaluation：在扰动、噪声或异常表达输入下评估方法的鲁棒性。
- DE weight optimization：使用 Differential Evolution 对安全重排和策略权重进行离线搜索。
- ablation：通过关闭或替换关键策略组件分析方法贡献。
- table export：从离线实验产物导出论文表格，避免手工统计和手工改写。

论文结果应以 `profiles/paper_eval.yaml` 和 `build/eval/` 下生成的离线实验产物为准。主实验不依赖远端 LLM 服务，也不以交互式 demo 的运行结果作为论文指标。

## 不纳入主实验的模块

以下模块保留在仓库中，但不纳入当前论文主实验：

- FastAPI：用于接口演示、调试和前后端联调，不作为论文主结果的评价入口。
- React frontend：用于控制台 demo 和可视化验证，不作为论文方法有效性的评价对象。
- ASR：用于未来语音输入链路验证，不参与当前离线文本实验。
- TTS：用于播报原型和交互演示，不参与当前离线评价指标。
- Radxa/hardware：用于未来端侧部署和资源约束验证，不表示当前论文已经完成长期硬件稳定性实验。
- LED/screen：用于硬件反馈预留和系统集成验证，不作为当前论文主结果。

这些模块的存在说明仓库具备系统原型方向，但论文主线仍限定在可复现的离线应急回复生成实验。

## 方法边界

HSC-RAG-DE 中的 HSC 指启发式安全约束组合策略，而不是单一模型结构。当前实现主要包括协议优先、低证据分流、安全护栏、安全重排和低随机性输出控制等策略。其目标是在高风险输入下减少不受控生成、幻觉扩散和不符合应急协议的回复。

DE 指使用 Differential Evolution 对安全重排/策略权重进行离线搜索。本文不声称提出新的进化算法本身，也不把 DE 作为独立算法贡献；DE 在本文中是权重校准和策略搜索工具，用于支持 HSC-RAG 链路的可复现配置选择。

## 复现实验入口

论文实验应使用以下 profile 和脚本：

```text
profiles/paper_eval.yaml
scripts/run_clean_eval.sh
scripts/run_robust_eval.sh
scripts/run_de_optimize.sh
scripts/run_ablation.sh
scripts/export_tables.sh
```

其中 `profiles/paper_eval.yaml` 是论文复现实验的确定性配置入口。该 profile 关闭远端 LLM、rewrite、语音输出和硬件输出，并将 trace 写入 `build/eval/` 相关路径。复现实验者应优先使用上述脚本，而不是从 API 服务、前端页面或语音/硬件链路推导论文结果。

## 当前不声称的内容

当前论文主实验不声称完成真实灾害现场医学验证。仓库中的应急回复链路用于离线实验和工程复现，不等同于经过现场医学、救援或伦理审批的真实部署系统。

当前论文主实验不声称替代专业救援。系统输出只能被理解为受约束的应急回复生成结果，不能替代救援人员、医生、急救调度员或其他专业人员的判断。

当前论文主实验不声称端侧硬件长期稳定部署已经完成。Radxa、LED、screen、语音播放等内容属于系统原型和未来部署验证方向，不构成本文离线实验结论的证据。

当前论文主实验不声称大语言模型自由生成能力是主要贡献。HSC-RAG-DE 更准确地说是离线约束式应急回复生成方法，其核心贡献在于协议优先、安全约束、低证据分流、安全重排和离线权重搜索等组合工程策略，而不是开放式对话生成能力。
