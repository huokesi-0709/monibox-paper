# 阶段 2 输入归一化说明

输入归一化模块位于 MoniBox / HSC-RAG-DE 主链路的前段，在 intent extraction、protocol matching 和 RAG search 之前执行。它的目标是把用户原始输入转换为更稳定的 `canonical_text`，同时保留可审计 trace，便于后续解释鲁棒性实验中的输入变化。

## 解决的问题

输入归一化主要处理以下开发阶段已观察到的输入噪声：

- ASR 错听：例如同音字、近音字或常见错别字导致的“退在留血”等表达。
- 口语噪声：例如“呃”“嗯”“那个”“就是”等不影响应急语义的填充词。
- 重复呼救：例如连续重复“救命救命救命”。
- 标点和 Unicode 不一致：例如全角标点、全角空格和不同 Unicode 形式。
- 简单救援短语归一化：例如把身体部位和出血表达归并到更稳定的文本形态。

这些处理用于提升 clean/robust evaluation 中路由、协议匹配和检索输入的一致性，不用于替代后续安全约束、协议判断或 RAG 证据校验。

## 不做什么

输入归一化不做医学判断，不推断用户没有说出的症状，不把否定表达改成肯定风险，也不把普通生活文本强行改写成应急表达。

例如：

- “我腿疼但是没有流血”不应被改成严重出血表达。
- “我没有喘不上气”不应被改写成肯定呼吸困难。
- “退群消息”不应把“退”改成“腿”。
- “穿衣服”不应把“穿”改成“喘”。

这些约束是阶段 2 的安全边界：归一化可以修正明确的 ASR 噪声，但不能创造新的高风险事实。

## Exact Correction 与 Fuzzy Context Correction

exact correction 是确定性的精确替换。规则来自内置高频错听和 `knowledge/asr_corrections.json` 中的 `corrections` 字典。只有当输入文本中出现完整 source 片段时，才替换为对应 target。

fuzzy context correction 来自 `knowledge/asr_corrections.json` 中的 `fuzzy_patterns.rules`。每条规则包含 `context_keywords`、`pattern` 和 `replacement`。该类规则只有在文本中出现至少一个上下文关键词时才允许执行。例如，只有在出血、伤口、止血等上下文中，才允许把“退”按规则纠正为“腿”。

执行顺序为：

```text
Unicode/标点规范化 -> 口语噪声移除 -> exact correction -> 救援短语归一化 -> fuzzy context correction -> 重复词折叠 -> final cleanup
```

fuzzy context correction 不能无上下文全局替换，这是为了降低普通文本和否定表达被误伤的风险。

## Trace 的作用

`NormalizedInput.trace_dict()` 会保留原有字段：

- `raw_text`
- `canonical_text`
- `corrections`
- `noise_removed`
- `repeated_terms_collapsed`

同时增加轻量统计字段：

- `changed`
- `num_corrections`
- `num_noise_removed`
- `num_repeated_terms_collapsed`

这些字段用于后续 benchmark 和论文 trace 统计，帮助区分鲁棒性提升来自 ASR 修正、口语噪声移除、重复折叠，还是下游协议/RAG/安全重排模块。

## 与 Robust Perturbation 和 Ablation 的关系

robust evaluation 可以构造 ASR 同音错误、filler noise、repetition、long context、multi-intent、negation conflict 和 out-of-scope distraction 等扰动样例。输入归一化负责处理其中可安全修正的表层噪声。

ablation 中可以关闭输入归一化，用于比较同一组 clean/robust 样例在有无归一化时的路由、协议命中、证据命中和安全输出差异。归一化 trace 应与预测结果一起保留，便于分析哪些样例受益于归一化，哪些样例应交由后续模块处理。
