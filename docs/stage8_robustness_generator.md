# 阶段 8：鲁棒性扰动数据生成器

阶段 8 的目标是为 robust evaluation 提供可复现的数据生成流程。生成器从 clean benchmark JSONL 读取样本，按固定规则生成扰动样本，并输出满足阶段 7 `BenchmarkCase` schema 的 robustness JSONL。

该阶段不引入 LLM，不扩展 gold evidence，不改变运行时主链路，也不修改 metrics 计算逻辑。

## 输入与输出

默认输入：

```bash
benchmarks/data/clean_dev.jsonl
```

默认输出：

```bash
benchmarks/data/robustness_dev.jsonl
```

推荐命令：

```bash
python -m benchmarks.generate_robustness \
  --input benchmarks/data/clean_dev.jsonl \
  --output benchmarks/data/robustness_dev.jsonl \
  --seed 42 \
  --max-per-case 3
```

也可以使用脚本：

```bash
scripts/generate_robustness.sh
```

## 复现控制

生成器使用 `random.Random(seed)`，不使用全局随机状态。同一输入、同一 `seed` 和同一 `max_per_case` 会得到稳定输出。

参数含义：

- `--seed`：控制候选扰动在 `max_per_case` 限制下的选择。
- `--max-per-case`：限制每条 clean case 最多派生多少条 robust case。
- `--include-generated`：默认启用，追加少量合成的 `out_of_scope` 与 `unsafe_induction` 样本。
- `--no-include-generated`：只生成从 clean case 派生的扰动样本。

输出顺序固定为：按 clean case 原始顺序遍历；每条 clean case 内按扰动类型顺序输出；最后追加 generated cases。

## 扰动类型

`asr_homophone`：模拟 ASR 同音或近音错误，例如“腿→退”“流血→留血”“喘不上气→穿不上气”“地震→地真”。主要用于测试输入归一化能否修复常见错听。

`filler_noise`：加入“呃”“啊”“咳咳”“那个”“救命救命”等口语噪声。主要用于测试口语噪声移除和后续意图抽取稳定性。

`repetition`：构造“喘不上气喘不上气”“被困被困”“好冷好冷”“害怕害怕”等重复呼救。主要用于测试重复折叠与鲁棒意图抽取。

`long_context`：在原 query 前后加入信号不稳、等待救援、碎石声、情绪表达等上下文。该扰动不应向低风险样本插入新的高优先级风险。

`multi_intent`：将当前 query 与另一个中低优先级或同等优先级 query 组合。若另一个 query 会引入更高优先级风险，则跳过该组合，避免保留错误标签。

`negation_conflict`：用于“没流血”“没有喘不上气”“不是被困”等标签变更型样本。这类样本不是语义保持扰动；例如从 severe bleeding case 派生“腿疼但是没流血”时，期望主意图应改为 `pain_or_injury`，不能继续按 severe bleeding 解释。

`out_of_scope`：合成少量非应急输入，例如天气、吃饭、闲聊。期望主意图为 `out_of_scope`，协议 id 为空。

`unsafe_induction`：合成少量诱导过度承诺或危险建议的输入，例如要求“保证获救”“止血带”“注射”“药物剂量”。该类样本用于安全边界和 guard 相关错误分析，不用于证明模型具备医学处置能力。

## 字段继承

从 clean case 派生的 robust case 默认继承：

- `risk_level`
- `expected_route`
- `expected_protocol_id`
- `expected_primary_intent`
- `expected_tags`
- `gold_chunk_ids`
- `unsafe_actions`
- `reference_reply`

并补充：

- `clean_id = clean.id`
- `canonical_id = clean.canonical_id or clean.id`
- `clean_query = clean.clean_query or clean.query`

标签变更型扰动会显式更新 `risk_level`、`expected_route`、`expected_protocol_id`、`expected_primary_intent`、`expected_tags` 和 `reference_reply`。

合成样本的 `clean_id` 与 `canonical_id` 可以为 `None`。

## gold evidence 边界

生成器不会编造 `gold_chunk_ids`。如果 clean 数据中的 `gold_chunk_ids` 为空，派生 robust 数据也会保持为空。

因此，当 `num_evidence_eval_cases = 0` 或分母较小时，`evidence_hit_at_3` 不能被解释为最终 RAG 证据能力结论。最终 SCI 实验仍需要补齐 gold evidence 标注。

## 数据集定位

当前 `robustness_dev.jsonl` 是 dev/smoke 数据，用于验证鲁棒性评估链路、trace 和 metrics，不等同最终论文 test set。

后续阶段使用方式：

- 阶段 9：比较 baselines 和 ablations 的 robust metrics。
- 阶段 10：DE 优化不应使用 final test set，可使用开发集或独立验证集。
- 阶段 11：汇总 robust metrics、扰动类型分布和 trace 统计。
