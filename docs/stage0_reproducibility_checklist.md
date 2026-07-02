# 阶段 0 复现边界验收清单

> [!WARNING]
> OBSOLETE / HISTORICAL: This document is retained only as project history. Do not use it as the current RAIR-RAG paper or reproduction source. Current canonical entry points are `docs/RAIR_RAG_routing_reproduction.md`, `docs/RAIR_RAG_downstream_reproduction.md`, `models/README.md`, and `models/llm/README.md`.

本文档记录阶段 0：论文级工程基线与研究边界确认的当前验收状态。阶段 0 的目标是让仓库能够明确区分论文主实验链路和 demo/原型链路，并为后续 SCI 实验扩展保留清晰入口。

## 验收项

- 论文实验链路和 demo 链路已区分：`docs/paper_scope.md` 明确说明主实验只覆盖离线 clean、robust、DE、ablation 和 table export；API、frontend、voice、hardware 等模块只用于演示、联调、原型验证或未来部署探索。
- 确定性 paper profile 已存在：`profiles/paper_eval.yaml` 是论文复现实验的默认配置入口。
- clean / robust / DE / ablation / export tables 脚本已存在：`scripts/run_clean_eval.sh`、`scripts/run_robust_eval.sh`、`scripts/run_de_optimize.sh`、`scripts/run_ablation.sh`、`scripts/export_tables.sh` 可作为论文实验入口。
- 远端 LLM 已在 paper profile 中关闭：`llm.backend: null`，`temperature: 0.0`，`stream: false`。
- rewrite 已在 paper profile 中关闭：`rewrite.enabled: false`，`rewrite.protocol_enabled: false`，`rewrite.low_evidence_enabled: false`。
- 语音和硬件输出已在 paper profile 中关闭：TTS backend 为空，LED 和 screen 均为 disabled。
- 离线实验产物边界已说明：论文结果应以 `build/eval/` 下的 predictions、summary、trace 和导出表格为准。
- 当前数据集性质已说明：现有 dev/evaluation 数据仍属于论文工程原型验证数据，最终 SCI 主实验需要扩展数据规模、补充更严格的 gold evidence 标注，并记录数据构建与质控流程。

## 当前状态

阶段 0 当前状态：通过，但带有后续阶段遗留任务。

该状态表示仓库已经具备论文主线边界说明、确定性 profile、离线实验入口和 demo 边界说明，可以进入后续实验扩展与结果固化阶段。但阶段 0 不表示最终 SCI 实验已经完成，也不表示数据规模、gold evidence、人工评估和统计检验已经达到投稿版本要求。

## 后续阶段遗留任务

- 扩展 clean 与 robust evaluation 数据规模，并区分 dev、validation 和 final reporting set。
- 为关键样例补充 gold evidence 标注，明确回复应依据的协议条目或知识片段。
- 固化人工评估表、评分规范和一致性检查流程。
- 记录正式实验环境、模型版本、embedding 版本和随机种子。
- 在 table export 后增加面向论文附录的结果审计说明，解释缺失值、异常样例和不纳入统计的情况。
