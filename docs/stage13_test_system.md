# 阶段 13：测试体系与质量门禁

> [!WARNING]
> OBSOLETE / HISTORICAL: This document is retained only as project history. Do not use it as the current RAIR-RAG paper or reproduction source. Current canonical entry points are `docs/RAIR_RAG_routing_reproduction.md`, `docs/RAIR_RAG_downstream_reproduction.md`, `models/README.md`, and `models/llm/README.md`.

阶段 13 的目标是把阶段 0 到阶段 12 的测试纳入统一质量门禁，使论文工程仓库具备可运行、可解释、可持续维护的测试入口。

## 本地推荐命令

统一入口：

```bash
bash scripts/run_tests.sh
```

当前脚本执行：

```bash
python -m pytest
```

全仓库 lint 的目标命令为：

```bash
python -m ruff check .
```

当前仓库仍存在少量历史 lint 债务，主要位于非论文主实验路径的日志、datetime 和性能规则；因此 full ruff 暂作为后续质量目标，不作为本阶段硬阻断。

## 测试分层

unit：覆盖纯函数、schema、metrics、SearchSpace、fitness、配置解析等快速确定性逻辑。

lightweight integration：使用 fake RAG、fake session、fake evaluator 或临时文件，覆盖 MoniSession trace、run_eval 输出、DE 小规模优化、export tables 等链路。

paper contract：覆盖 `profiles/paper_eval.yaml`、论文脚本入口、benchmark schema、paper trace、paper docs、阶段文档和质量门禁。

manual/slow：真实 benchmark 全流程、完整 160 次 DE、真实 `rag.db`、语音、硬件、ASR/TTS 模型和现场部署验证。这类测试不进入默认 CI。

## CI 范围

CI 只运行轻量测试和阶段 13 质量门禁 lint：

```bash
python -m pytest
python -m ruff check tests/test_stage13_quality_gates.py
```

CI 不运行真实 benchmark，不运行完整 DE，不调用远端 LLM，不依赖真实硬件、TTS、ASR 模型或 `rag.db`，也不上传 `build/eval` 产物。

## 安全边界

测试不得要求真实 API key，例如 `OPENAI_API_KEY`、`DEEPSEEK_API_KEY` 或其他远端模型密钥。

测试不得把 final test set 用于 DE 调参，不得在测试中写死真实用户隐私输入。

测试可以使用构造样本、fake evaluator 和临时目录，但不能把 dev/smoke 结果写成最终 SCI 结论。

## 后续维护规则

新增阶段或模块时必须补测试。

修改 metrics、schema、trace、profile 或导表字段时，必须同步更新对应测试。

论文结果必须来自 `build/eval` 与阶段 11 导出的表格，不应在测试或文档中编造最终结果。

当历史 lint 债务清理完成后，应将 `scripts/run_tests.sh` 与 CI 升级为同时执行：

```bash
python -m pytest
python -m ruff check .
```
