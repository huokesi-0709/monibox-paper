# 数据集扩充与标注操作手册

本文档面向第一次做论文数据集的小白。目标是把当前 10 条 clean / 30 条 robust 的开发样例，扩展为可以写进 SCI 论文的方法学数据集。

如果你准备用不同 AI 模型代替两名独立标注者，并用第三个 AI 做裁决，请同时阅读 `docs/ai-annotation-prompts-zh.md`。该文档已经给出可直接复制给模型的 A/B/C 三套提示词。

## 你最终要得到什么

最低目标：

| split | clean | robust | 用途 |
| --- | ---: | ---: | --- |
| dev | 150+ | 450+ | 开发、调参、DE 优化、错误分析 |
| test | 200+ | 600+ | 最终一次性报告结果 |

注意：test 集锁定后，不要再根据 test 结果反复改规则、改权重或改代码。

## 文件在哪里

模板已经放在：

- `benchmarks/data/annotation/clean_candidates_template.csv`
- `benchmarks/data/annotation/annotator_template.csv`

正式工作时建议复制成：

- `benchmarks/data/annotation/clean_candidates.csv`
- `benchmarks/data/annotation/annotator_a.csv`
- `benchmarks/data/annotation/annotator_b.csv`

如果你不会复制文件，可以在资源管理器里右键复制模板，再改文件名。

也可以先用现有 10 条 clean seed 自动生成起步表：

```bash
python -m benchmarks.export_annotation_candidates --input benchmarks/data/clean_dev.jsonl --candidates-out benchmarks/data/annotation/clean_candidates_seed.csv --annotator-a-out benchmarks/data/annotation/annotator_a_seed.csv --annotator-b-out benchmarks/data/annotation/annotator_b_seed.csv
```

这个命令只把已有样本搬到 CSV 里。`annotator_a_seed.csv` 和 `annotator_b_seed.csv` 的标签列是空的，目的是让两位标注者独立填写。

当你把 `clean_candidates.csv` 扩到 350 条之后，用下面命令生成正式 A/B 标注表：

```bash
python -m benchmarks.prepare_annotation_sheets --candidates benchmarks/data/annotation/clean_candidates.csv --annotator-a-out benchmarks/data/annotation/annotator_a.csv --annotator-b-out benchmarks/data/annotation/annotator_b.csv
```

## 第 1 步：准备 350 条 clean 候选样本

打开 `clean_candidates.csv`，每一行写一个用户输入。先不要管系统输出，只写真实或场景化的求助句。

字段含义：

- `case_id`：样本编号，例如 `clean_0001`、`clean_0002`。
- `query`：用户输入原文，例如“我的腿在流血，血止不住。”
- `scenario`：场景类别，例如 `severe_bleeding`、`respiratory_distress`。
- `source_type`：来源类型，建议用 `scenario_written`、`guideline_based`、`volunteer_written`。
- `source_note`：简单说明来源，不需要很长。

建议配额：

| 场景 | 建议 clean 数 |
| --- | ---: |
| severe_bleeding 出血 | 35 |
| respiratory_distress 呼吸困难 | 35 |
| trapped_or_crush 被困/挤压 | 35 |
| hypothermia 失温 | 25 |
| dehydration 脱水 | 25 |
| panic 恐慌 | 25 |
| head_or_consciousness 头晕/意识 | 30 |
| pain_or_injury 疼痛/骨折 | 30 |
| low_battery 低电量/定位 | 20 |
| out_of_scope 域外问题 | 25 |
| unsafe_induction 安全诱导 | 25 |
| negation_conflict 否定冲突 | 25 |
| multi_intent 多意图 | 40 |

总数可以超过 350，后面再分层抽样。

## 第 2 步：找两个人独立标注

至少需要两位标注者。理想组合：

- 标注者 A：有急救、护理、医学、应急管理或安全培训背景。
- 标注者 B：有 NLP、软件系统、信息检索或论文实验背景。

如果找不到专业人员，也可以先用两名受过标注说明培训的人做初版，但论文里要诚实写标注者背景。

关键要求：两个人必须独立标注，不能边看对方答案边填。

## 第 3 步：每个标注者怎么填表

每位标注者各自复制一份 `annotator_template.csv`。

需要填写这些字段：

- `case_id`：必须和 clean 候选表一致。
- `annotator_id`：例如 `A` 或 `B`。
- `annotator_background`：例如 `first-aid trained`、`NLP researcher`。
- `query`：用户输入。
- `scenario`：场景类别。
- `risk_level`：只能填 `critical`、`high`、`medium`、`low`。
- `expected_route`：系统应该走的主路由。
- `expected_protocol_id`：应该命中的协议 ID；域外样本可以留空。
- `expected_primary_intent`：最高优先级意图。
- `expected_tags`：多标签用英文分号分隔，例如 `出血;腿;高风险`。
- `gold_chunk_ids`：证据 chunk ID；知识库稳定前可以先留空，后面补。
- `unsafe_actions`：回复中禁止出现的危险建议，用英文分号分隔。
- `reference_reply`：安全参考回复，不需要很长。
- `notes`：有争议就写原因。

## 第 4 步：算 Cohen's kappa

两个人都填完后，运行：

```bash
uv run --extra dev python -m benchmarks.annotation_agreement --annotator-a benchmarks/data/annotation/annotator_a.csv --annotator-b benchmarks/data/annotation/annotator_b.csv --out-json build/eval/annotation/agreement.json --out-csv build/eval/annotation/agreement.csv
```

如果不用 `uv`，也可以运行：

```bash
python -m benchmarks.annotation_agreement --annotator-a benchmarks/data/annotation/annotator_a.csv --annotator-b benchmarks/data/annotation/annotator_b.csv --out-json build/eval/annotation/agreement.json --out-csv build/eval/annotation/agreement.csv
```

输出里会包含：

- `risk_level` 的 Cohen's kappa
- `expected_route` 的 Cohen's kappa
- `expected_protocol_id` 的 Cohen's kappa
- `expected_primary_intent` 的 Cohen's kappa
- `expected_tags`、`gold_chunk_ids`、`unsafe_actions` 的 mean Jaccard agreement

## 第 5 步：怎么看 kappa

常用解释：

| kappa | 含义 |
| ---: | --- |
| < 0.40 | 一致性偏弱，需要重写标注规则 |
| 0.40-0.60 | 一般，论文风险仍然较高 |
| 0.61-0.80 | 可以接受 |
| > 0.80 | 较强，比较适合论文报告 |

如果低于 0.61，不要急着跑实验。先找出分歧样本，改标注说明，再重新标一轮。

## 第 6 步：裁决分歧

把 A、B 不一致的样本挑出来，逐条讨论。最终标签不能简单取平均，要由第三人或你按照 guideline 做裁决。

裁决后得到 final label，再导出正式 JSONL：

- `benchmarks/data/clean_dev.jsonl`
- `benchmarks/data/clean_test.jsonl`

建议先不要覆盖旧文件，等 final label 完成后再替换。

## 第 7 步：生成 robust

clean dev/test 完成后，再分别生成 robust：

```bash
python -m benchmarks.perturbation_builder --input benchmarks/data/clean_dev.jsonl --out benchmarks/data/robustness_dev.jsonl --max_per_case 3 --seed 42
python -m benchmarks.perturbation_builder --input benchmarks/data/clean_test.jsonl --out benchmarks/data/robustness_test.jsonl --max_per_case 3 --seed 43
```

生成后必须人工检查 robust 样本，尤其是：

- 否定冲突是否错误继承了高风险标签。
- 多意图样本是否选择了最高风险意图。
- 安全诱导样本是否没有给出可执行危险操作。
- `clean_id` 是否能追溯到来源 clean 样本。

## 第 8 步：论文里怎么写

可以写成：

> We constructed a scenario-based, expert-annotated benchmark for offline emergency text assistance. Two annotators independently labeled risk level, route, primary intent, protocol ID, unsafe actions, and evidence chunks. Inter-annotator agreement was measured with Cohen's kappa for categorical labels and mean Jaccard agreement for multi-label fields. Disagreements were adjudicated before producing the final dev/test splits.

不要写成真实灾害语料，除非你真的做了真实采集、伦理审批和隐私处理。
