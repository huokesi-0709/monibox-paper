# HSC-RAG-DE 论文写作计划

## 论文定位

本文是方法与实验复现论文，主方法为 HSC-RAG。MoniBox 仅作为 prototype validation platform，用于展示离线链路、trace 和端侧可运行性。pymoo Differential Evolution 仅作为离线权重优化工具，不是本文算法贡献主体。

## 目标投稿稿件结构

采用外刊论文结构：

1. Title
2. Abstract
3. Introduction
4. Related Work
5. Method
6. Experimental Setup
7. Results
8. Discussion
9. Conclusion

不采用本科论文式“需求分析、系统设计、系统实现、系统测试”结构。系统实现细节只服务于方法复现和实验可信度。

## 中文先行策略

先在 `paper/zh/` 写中文稿，稳定术语、方法公式、实验协议和结果表格后，再迁移到 `paper/en/manuscript.md`。英文稿不得重新发明术语，应以 `paper/zh/00_术语表.md` 和 `paper/en/glossary.md` 为准。

## 当前写作任务

- 完成 Introduction 七段逻辑。
- 完成 Method 公式和模块说明。
- 固化 dev/test 分离的实验协议。
- 用 `experiments.export_tables` 自动导出论文表格。
- 用 trace case study 展示可解释性。

## 安全边界写法

论文中必须反复明确：系统不替代专业救援，不保证救援成功，不提供医学诊断，不给出药物剂量、注射、输液等高风险医疗操作细节。
