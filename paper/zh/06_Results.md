# Results

## Main Results

本节放置 clean benchmark 上 rule-only、vanilla-rag、rag-guard、hsc-rag-manual 和 hsc-rag-de 的主结果表。表格应由 `python -m experiments.export_tables` 自动导出，不手工改数字。

## Robustness Results

本节报告 robustness benchmark 上的 route accuracy、primary intent accuracy、protocol false trigger rate、robust consistency 和 unsafe response rate。

## Ablation Results

本节展示各模块移除后的性能变化，用于说明输入归一化、多意图、协议门控、安全重排、低证据分流、输出护栏和 DE 调权的贡献。

## DE Effect

本节比较 manual policy 与 DE policy。DE 只作为离线校准工具，结果应报告 fitness、clean route accuracy、robust route accuracy、高风险漏检率和 unsafe response rate。

## Trace Case Study

本节选择若干 trace 案例，展示 raw text、canonical text、corrections、primary intent、protocol confidence、top chunks、guard reasons 和 final reply。
