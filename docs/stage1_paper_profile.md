# 阶段 1 论文专用 Profile 与配置契约

`profiles/paper_eval.yaml` 是 MoniBox / HSC-RAG-DE 论文复现实验的专用配置契约。它用于 clean evaluation、robust evaluation、DE weight optimization、ablation 和 table export 等离线实验，不用于 API、frontend、voice、hardware 或本地 demo 调试。

## 与其他 Profile 的区别

`profiles/base.yaml` 是全平台默认配置，包含普通运行时需要的默认 LLM、rewrite、TTS、hardware 和 debug 参数。

`profiles/windows.yaml`、`profiles/radxa.yaml` 或其他平台 profile 面向本地开发、端侧联调和 demo 运行，可以根据设备、语音链路或硬件状态调整。

`profiles/paper_eval.yaml` 面向论文复现实验。它显式写入关键实验参数，减少对 `base.yaml` 的隐式依赖，并将远端 LLM、rewrite、TTS、LED、screen 等非主实验链路默认关闭。

## 默认关闭项

paper profile 默认关闭远端 LLM，是为了让论文主实验保持离线、确定性和低随机性，不被外部 API 状态、网络延迟或模型版本变化影响。

paper profile 默认关闭 rewrite，是为了避免后处理改写引入额外随机性或隐藏主链路的协议/检索/安全重排行为。

paper profile 默认关闭 TTS 和 hardware，是因为语音播报、LED、screen 和端侧硬件联调属于系统原型或未来部署验证，不是当前论文主实验指标。

## 环境变量覆盖策略

普通 profile 仍保留历史环境变量覆盖能力，便于本地调试和设备联调。

`paper_eval` 默认禁止非机密环境变量覆盖，包括旧式 `TTS_BACKEND`、`REWRITE_ENABLED`、`LLM_TEMPERATURE`，以及嵌套式 `LLM__BACKEND`、`SPEECH__TTS__BACKEND` 等。这样可以避免开发机残留环境变量悄悄改变论文实验配置。

如果确需临时调试 paper profile，可显式设置：

```bash
ALLOW_PAPER_ENV_OVERRIDE=1
```

正式复现实验不建议启用该变量。

## 推荐入口

论文实验脚本推荐使用：

```bash
bash scripts/run_clean_eval.sh
bash scripts/run_robust_eval.sh
bash scripts/run_de_optimize.sh
bash scripts/run_ablation.sh
bash scripts/export_tables.sh
```

这些入口应通过 `--profile-file profiles/paper_eval.yaml` 绑定论文配置。若 `--profile-file` 指向的文件不存在，评估入口应直接失败，而不是静默 fallback 到 `base.yaml` 或其他 profile。

## 后续 Profile 派生原则

如果后续需要 final reporting profile，应从 `profiles/paper_eval.yaml` 派生，并只调整正式报告所需的实验参数、数据路径或 trace 路径。不要从 demo、voice、windows 或 radxa profile 派生最终论文实验配置。
