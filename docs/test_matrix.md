# 测试矩阵

本文件索引当前论文工程仓库的主要测试文件及其覆盖阶段。

| 测试文件 | 覆盖阶段 | 说明 |
| --- | --- | --- |
| `tests/test_stage0_paper_contract.py` | 阶段 0 | paper profile、脚本和数据入口契约 |
| `tests/test_stage0_repo_hygiene.py` | 阶段 0 | `.gitignore`、`.env.example` 和仓库卫生 |
| `tests/test_stage1_paper_profile.py` | 阶段 1 | paper profile 配置锁定与环境变量保护 |
| `tests/test_input_normalizer.py` | 阶段 2 | 输入归一化、ASR correction、trace 字段 |
| `tests/test_intent_extractor.py` | 阶段 3 | 风险感知多意图、否定、tags、body/scene |
| `tests/test_protocol_confidence.py` | 阶段 4 | 协议匹配置信度、否定冲突、event trigger |
| `tests/test_hsc_rag_scoring.py` | 阶段 5 | HSC-RAG scoring、rerank、vector-only 消融 |
| `tests/test_paper_trace.py` | 阶段 6 | paper trace schema、JSONL、benchmark prediction trace |
| `tests/test_benchmark_schema_metrics.py` | 阶段 7 | benchmark schema、metrics、分母计数 |
| `tests/test_run_eval_outputs.py` | 阶段 7/9 | run_eval 输出、baseline metadata、ablation results |
| `tests/test_benchmark_metrics.py` | 阶段 7 | 既有 metrics 和 run_eval smoke |
| `tests/test_robustness_generator.py` | 阶段 8 | deterministic robust perturbation generator |
| `tests/test_benchmark_methods_ablations.py` | 阶段 9 | methods、ablations、disabled_modules |
| `tests/test_de_pymoo_optimize.py` | 阶段 10 | SearchSpace、fitness、fake DE optimization |
| `tests/test_export_tables.py` | 阶段 11 | result tables、trace audit、空输入导出 |
| `tests/test_stage12_paper_docs.py` | 阶段 12 | paper 顶层中文稿和复现文档 |
| `tests/test_paper_docs.py` | 论文文档 | 既有中文/英文论文分章节文档 |
| `tests/test_stage13_quality_gates.py` | 阶段 13 | 统一测试入口、CI、质量门禁与安全边界 |
