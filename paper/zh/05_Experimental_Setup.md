# Experimental Setup

## Research Questions

RQ1：HSC-RAG 相比 rule-only、vanilla RAG 和 RAG+Guard 是否提高 route accuracy 与安全性？

RQ2：输入归一化、多意图抽取、协议门控、安全重排、低证据分流和输出护栏分别带来什么贡献？

RQ3：在 ASR 错听、口语噪声、重复输入、长上下文、多意图、否定冲突、域外输入和危险诱导下，HSC-RAG 是否保持鲁棒？

RQ4：DE 离线调权是否优于 manual policy？

## Datasets

实验使用 clean dev/test 与 robustness dev/test。dev 只用于开发、阈值选择和 DE 调权；test 只用于最终报告。任何形式的 DE 优化不得使用 test 数据。

## Methods

比较方法包括 rule-only、vanilla-rag、rag-guard、hsc-rag-manual 和 hsc-rag-de。

## Ablations

消融项包括 w/o input normalization、w/o multi-intent extraction、w/o negation handling、w/o protocol gate、w/o safety rerank、w/o low-evidence routing、w/o safety guard、w/o DE optimization。

## Metrics

主要指标包括 route accuracy、protocol hit rate、high-risk recall、high-risk miss rate、evidence hit@k、unsafe response rate、unsupported claim rate、primary intent accuracy、protocol false trigger rate、robust consistency、latency。

## Safety Boundary

所有实验只评价应急信息辅助能力，不评价医疗诊断能力，也不声称系统能替代专业救援或保证获救。
