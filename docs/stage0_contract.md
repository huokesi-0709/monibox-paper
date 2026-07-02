# 阶段 0 论文复现契约测试说明

> [!WARNING]
> OBSOLETE / HISTORICAL: This document is retained only as project history. Do not use it as the current RAIR-RAG paper or reproduction source. Current canonical entry points are `docs/RAIR_RAG_routing_reproduction.md`, `docs/RAIR_RAG_downstream_reproduction.md`, `models/README.md`, and `models/llm/README.md`.

`tests/test_stage0_paper_contract.py` 是阶段 0 的轻量契约测试。它不是功能测试，也不运行完整 clean、robust、DE、ablation 或 table export 实验。

该测试只检查论文复现实验基线是否仍然存在：

- `profiles/paper_eval.yaml` 必须存在。
- paper profile 必须保持离线、确定性、低随机性设置，包括关闭远端 LLM、rewrite、TTS、LED 和 screen，并开启 runtime trace。
- clean、robust、DE、ablation 和 export tables 五个脚本必须存在。
- `clean_dev.jsonl` 和 `robustness_dev.jsonl` 两个 benchmark 数据入口必须存在。

这些检查用于防止后续开发在无意中破坏论文复现实验入口。它们不验证 API、frontend、voice 或 hardware demo 是否可运行，也不要求 `build/eval/`、真实模型文件或完整实验产物存在。

建议在阶段 0 及后续论文实验开发前运行：

```bash
uv run --extra dev pytest tests/test_stage0_paper_contract.py
```
