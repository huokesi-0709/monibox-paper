# 数据集审计报告

- 生成时间：2026-06-26T06:52:04.698251+00:00
- 输入目录：`D:\projects\monibox-Y\monibox\benchmarks\data`
- 输出目录：`D:\projects\monibox-Y\monibox\build\eval\dataset_audit`

## 结论

- 数据总量是否为 1500：是（当前 1500 条）。
- dev/test 是否泄漏：否（泄漏 canonical_id 数：0）。
- 每个风险类别样本是否明显失衡：否。
- 是否存在字段缺失：否（字段缺失记录数：0）。
- 是否存在无法参与评测的样本：否（严重问题记录数：0）。
- 是否可以支撑当前论文的数据集统计：是。
- gold_chunk_ids 为空比例：1500/1500 （100.0%）。
- evidence_hit 指标建议仅作为诊断指标，不宜作为强主结论，原因是 gold_chunk_ids 为空比例过高。

## 文件样本数

| 数据文件 | split | suite | 样本数 |
| --- | --- | --- | --- |
| clean_dev | dev | clean | 150 |
| robustness_dev | dev | robust | 450 |
| clean_test | test | clean | 225 |
| robustness_test | test | robust | 675 |

## 分布摘要

### 风险等级分布

| 数据文件 | low | medium | high | critical |
| --- | --- | --- | --- | --- |
| clean_dev | 22 | 45 | 24 | 59 |
| robustness_dev | 66 | 135 | 72 | 177 |
| clean_test | 33 | 67 | 37 | 88 |
| robustness_test | 99 | 201 | 111 | 264 |

### 扰动类型分布

| 数据文件 | clean | filler_noise | long_context | repetition |
| --- | --- | --- | --- | --- |
| clean_dev | 150 | 0 | 0 | 0 |
| robustness_dev | 0 | 150 | 150 | 150 |
| clean_test | 225 | 0 | 0 | 0 |
| robustness_test | 0 | 225 | 225 | 225 |

### 协议分布

| 数据文件 | <empty> | prot_airway_dust | prot_battery_critical_shutdown | prot_bleeding_control | prot_building_collapse_trapped | prot_chest_pain | prot_crush_pressure_long | prot_darkness_visibility | prot_dehydration_thirst | prot_despair_keep_alive | prot_head_injury_confusion | prot_hypothermia | prot_injury_fracture | prot_low_battery_degrade | prot_no_response_long_wait | prot_numbness_pressure | prot_panic_breathing | prot_rescue_voice_heard | prot_respiratory_distress | prot_secondary_collapse_risk | prot_smoke_fire_airway | prot_stuck_immobile | prot_syncope_blackout | prot_wet_cold_flood |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean_dev | 22 | 2 | 4 | 17 | 5 | 2 | 9 | 2 | 10 | 2 | 6 | 6 | 12 | 3 | 2 | 2 | 4 | 2 | 14 | 3 | 2 | 4 | 11 | 4 |
| robustness_dev | 66 | 6 | 12 | 51 | 15 | 6 | 27 | 6 | 30 | 6 | 18 | 18 | 36 | 9 | 6 | 6 | 12 | 6 | 42 | 9 | 6 | 12 | 33 | 12 |
| clean_test | 33 | 8 | 4 | 26 | 9 | 3 | 14 | 3 | 15 | 3 | 9 | 9 | 18 | 6 | 3 | 3 | 6 | 3 | 14 | 5 | 3 | 5 | 17 | 6 |
| robustness_test | 99 | 24 | 12 | 78 | 27 | 9 | 42 | 9 | 45 | 9 | 27 | 27 | 54 | 18 | 9 | 9 | 18 | 9 | 42 | 15 | 9 | 15 | 51 | 18 |

### 主意图分布

| 数据文件 | respiratory_distress | severe_bleeding | trapped_or_crush | head_or_consciousness | collapse_aftershock | hypothermia | dehydration | pain_or_injury | low_battery | panic | out_of_scope |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean_dev | 18 | 17 | 20 | 17 | 3 | 10 | 10 | 16 | 7 | 10 | 22 |
| robustness_dev | 54 | 51 | 60 | 51 | 9 | 30 | 30 | 48 | 21 | 30 | 66 |
| clean_test | 25 | 26 | 31 | 26 | 5 | 15 | 15 | 24 | 10 | 15 | 33 |
| robustness_test | 75 | 78 | 93 | 78 | 15 | 45 | 45 | 72 | 30 | 45 | 99 |

## 泄漏与对应关系检查

- dev/test canonical_id 泄漏数：0
- robust 样本无法找到 clean 对应项数量：0
- robust 样本只能跨 split 找到 clean 对应项数量：0

## 空字段与安全标注

- unsafe_actions 为空样本数：0
- expected_protocol_id 为空样本数：220。这类样本保留用于 protocol_false_trigger_rate，不按字段缺失处理。
- gold_chunk_ids 为空样本数：1500

## Warnings

- [high_empty_gold_chunk_ratio] gold_chunk_ids 为空比例为 100.0%；evidence_hit 应仅作为诊断指标，不宜作为强主结论

## Errors

- 无

