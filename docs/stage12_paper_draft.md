# 阶段 12：论文中文稿与 paper 文档目录

> [!WARNING]
> OBSOLETE / HISTORICAL: This document is retained only as project history. Do not use it as the current RAIR-RAG paper or reproduction source. Current canonical entry points are `docs/RAIR_RAG_routing_reproduction.md`, `docs/RAIR_RAG_downstream_reproduction.md`, `models/README.md`, and `models/llm/README.md`.

阶段 12 新增 `paper/` 顶层论文工作目录，用于承接阶段 0 到阶段 11 的工程基线、复现实验流程、表格导出和论文写作。

新增文件包括：

- `paper/README.md`
- `paper/manuscript_zh.md`
- `paper/figures.md`
- `paper/tables.md`
- `paper/reproducibility.md`

同时新增本阶段说明文档：

- `docs/stage12_paper_draft.md`

## 中文稿定位

`paper/manuscript_zh.md` 是中文工作稿，不是最终投稿版。当前稿件用于整理方法边界、实验设置、结果表引用位置和局限性说明。

稿件中的实验结果保持占位表引用形式，结果必须来自阶段 11 导出的 `build/eval/*.csv` 或 `build/eval/tables/*.md`，不得手写或编造数值。

## 当前占位内容

以下内容仍需后续补充：

- 正式参考文献和引用编号；
- 最终论文图像文件；
- 扩展后的最终数据集统计；
- gold evidence 标注后的证据指标解释；
- final test set 的一次性报告结果。

## 后续阶段

阶段 13 将补充测试体系与论文工程质量检查。后续写论文中文稿或英文稿时，应继续遵守以下边界：

- clean_dev / robustness_dev 是 dev/smoke 数据，不是最终 SCI test set；
- 不宣称医学诊断能力；
- 不宣称替代专业救援；
- 不宣称保证救援成功；
- DE 权重只在开发集上优化，final test set 不得用于调参。
