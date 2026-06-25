# Formal Evaluation Calibration Notes

本文件记录正式实验中的 dev-only 校准流程，避免后续论文写作时混淆 dev/test 使用边界。

## 数据边界

- 校准仅使用 `benchmarks/data/clean_dev.jsonl` 与 `benchmarks/data/robustness_dev.jsonl`。
- `benchmarks/data/clean_test.jsonl` 与 `benchmarks/data/robustness_test.jsonl` 只在规则冻结后用于最终报告。
- 不根据 test 错误继续调参或补规则。

## 本轮冻结规则

本轮校准补充了 `runtime/intent_extractor.py` 中的灾害/急救意图触发词，覆盖 dev 错例中遗漏的表达，例如出血、呼吸困难、受困/挤压、余震/坍塌、头部/意识、失温、脱水、疼痛受伤、低电量等。

同时加入了假设性建议问题过滤：例如“如果被压住了，我是不是应该硬拉出来？”这类泛化提问不作为真实受困事件触发。

`runtime/protocol_matcher.py` 增补了部分协议 ID 到风险类别的推断，用于让已有协议与新增意图类别更稳定地连接。

`knowledge/protocols.json` 增补了协议别名，范围包括坍塌/余震、出血、呼吸困难、胸痛、烟雾、挤压、头部/意识、受伤骨折、晕厥、湿冷、惊恐、麻木、受困、脱水、失温、低电量等协议。别名均来自 dev 错例暴露出的表达形式；写入后即冻结规则，再运行 test。

## 验证结果

冻结前 dev 结果约为 route/intent `0.6133`；校准后：

- `clean_dev`: route/intent `0.9733`
- `robust_dev`: route/intent `0.9733`
- `clean_dev`: `hsc-rag-de` protocol hit rate `0.6563`
- `robust_dev`: `hsc-rag-de` protocol hit rate `0.6563`

冻结后 test 结果输出在：

- `build/eval/formal_protocol_calibrated/main_results_overview.csv`
- `build/eval/formal_protocol_calibrated/paired_significance_vs_rule_only.csv`

最终 test 主要结果：

- `clean_test`: `hsc-rag-de` route/intent `0.9244`
- `robust_test`: `hsc-rag-de` route/intent `0.9244`
- `clean_test`: `hsc-rag-de` protocol hit rate `0.6510`
- `robust_test`: `hsc-rag-de` protocol hit rate `0.6510`
- `clean_test`: `hsc-rag-de` protocol false-trigger rate `0.0909`
- `robust_test`: `hsc-rag-de` protocol false-trigger rate `0.1919`
- unsafe response rate: `0.0000`
- high-risk recall: `0.9860`

## 注意事项

当前 `hsc-rag-*` 与 `rule-only` 在 route/intent 上同分，说明主提升来自共享的意图规则链，而非 RAG 排序模块本身。论文中不能表述为 HSC-RAG-DE 在 route/intent 上显著优于 rule-only；可以表述为校准后的安全意图识别模块在 clean/robust test 上达到较高召回和一致性。

协议命中率已经从旧版 `0.3333` 提升至 `0.6510`，但 `rule-only` 的 protocol hit rate 为 `0.6823`。因此论文中不应把 HSC-RAG-DE 描述为 protocol hit rate 最优；更合适的表述是：HSC-RAG-DE 在保持相近 route/intent 与 high-risk recall 的同时，大幅降低了协议误触发率。clean test 中 `rule-only` false-trigger rate 为 `1.0000`，`hsc-rag-de` 为 `0.0909`；robust test 中分别为 `1.0000` 与 `0.1919`。

McNemar 配对检验表显示，`hsc-rag-de` 与 `rule-only` 在 route/intent 上无差异，p = `1`；`vanilla-rag` 与 `rag-guard` 显著差于 `rule-only`。论文写作时应避免把 p = `1` 误写成“无效实验”，而应解释为二者在该指标上的逐例预测完全一致。
