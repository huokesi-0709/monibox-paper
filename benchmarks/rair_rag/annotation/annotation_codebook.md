# RAIR-RAG-Bench 人工标注指南

## 1. 标注目标

RAIR-RAG-Bench 面向离线灾害应急 RAG 的检索前风险路由。标注目标不是医学诊断，也不是生成最终急救回复，而是把受困者第一人称输入转化为可靠的风险上下文，供协议门控、RAG 检索和安全回复使用。

本文只把 `negation_conflict` 和 `multi_intent` 作为核心语义扰动。ASR 同音错、呼吸类错听、口语噪声、重复表达、域外/边界输入可以作为背景、预处理标签或补充实验，不作为主贡献。

每条样本至少标注：`positive_risks`、`negated_risks`、`primary_intent`、`secondary_intents`、`operational_constraints`、`expected_route`、`should_not_trigger`。如果样本使用了待确认中文来源支撑的标签，发布 gold 前必须完成来源确认。

## 2. 标签来源

风险标签体系来自 `benchmarks/rair_rag/annotation/risk_taxonomy.yaml`。其中 WHO-ICRC Basic Emergency Care 仅作为医学风险识别依据，不把专业医疗操作直接转成普通受困者指令；WHO Psychological First Aid 仅用于心理压力下的稳定化和支持性互动，不用于心理诊断或治疗。

当前 `crush_injury`、`trapped_or_entrapment`、`aftershock_or_collapse_hazard`、`dehydration_or_resource_deprivation` 含有中文官方资料的 `pending_source_confirmation`。这些标签可以进入试标，但最终 gold 发布前必须补足来源记录，或在数据说明中明确排除未确认样本。

## 3. 风险标签定义

- `respiratory_distress`：喘不上气、喘不过气、呼吸困难、吸不上气、窒息、缺氧、憋得厉害。`胸闷` 单独出现有争议，需结合喘不上气、缺氧、被压、烟尘、持续加重等上下文。
- `severe_bleeding_or_shock`：流血、出血、血止不住、很多血、喷血、冒血，以及脸色发白、发冷出汗等休克线索。被明确否定时不得触发出血协议。
- `trauma_or_fracture`：受伤、骨折、断了、扭伤、肿了、变形、砸到、麻了、无法活动、疼痛。`疼` 和 `痛` 是宽触发词，需结合身体部位、受伤机制、砸到、肿胀、麻木、变形等上下文。
- `crush_injury`：身体部位被重物压住、挤压、长时间埋压，可能伴随医学挤压伤风险。如果只是空间上出不去、身体没有受压，优先考虑 `trapped_or_entrapment`。
- `altered_consciousness_or_head_injury`：头晕、意识不清、昏迷、快晕、眼前发黑、撞到头、头被砸、想吐、记不清。`想吐` 单独出现较宽，需结合头部撞击、意识异常或严重眩晕。
- `hypothermia`：好冷、很冷、发冷、失温、哆嗦、湿透、体温低、冻僵。普通天气冷但无受困、湿冷或身体症状时不宜强触发。
- `psychological_distress`：害怕、恐慌、慌、崩溃、想哭、发抖、脑子很乱、撑不住。单独出现时可作为主意图；与高危医学/环境风险共现时通常作为次意图。
- `trapped_or_entrapment`：被困、困住、埋住、卡住、废墟里、出不去、门打不开。`动不了` 可能来自骨折、压迫、恐慌或空间受困，需结合上下文。
- `aftershock_or_collapse_hazard`：余震、又震、还在晃、快塌了、倒塌、墙在裂、掉东西、楼要塌。回忆“刚才有余震”不等于当前仍有坍塌危险。
- `dehydration_or_resource_deprivation`：很渴、没水、缺水、嘴干、没吃的、没力气、被困很久、没有食物。普通口渴但无灾害受困上下文时不宜高权重触发。
- `low_battery`：手机没电、快没电、电量低、快关机、只剩百分之五。它是 `operational_constraints`，不是医学风险，不能作为医学主意图。
- `out_of_scope`：写诗、做饭、股票、游戏攻略、八卦、作业答案、闲聊等明显脱离灾害应急场景的输入。它是 `safety_boundary`，不是医学风险。

## 4. 否定冲突定义

当文本中出现某个风险词，但用户明确否定该风险存在时，标为 `negation_conflict`。被否定的风险写入 `negated_risks`，不得作为 `primary_intent`，对应协议写入 `should_not_trigger`。

判定例：

```text
句子：我腿疼但是没流血
risk_mentions: pain, bleeding
positive_risks: trauma_or_fracture
negated_risks: severe_bleeding_or_shock
primary_intent: trauma_or_fracture
should_not_trigger: prot_bleeding_control
```

典型否定包括：`没流血`、`没有呼吸困难`、`不是喘不上气`、`没头晕`、`没撞到头`、`不冷`、`没被困`、`没有压住`。如果一句话自相矛盾，例如“没流血但血止不住”，不要自动决定，进入仲裁。

## 5. 多意图输入定义

当同一输入包含两个或以上风险、环境危险或运行约束时，标为 `multi_intent`。标注者必须保留所有有效风险，但只选择一个 `primary_intent`。运行约束写入 `operational_constraints`，不写入 `secondary_intents`。

判定例：

```text
句子：我喘不上气，手机快没电了
positive_risks: respiratory_distress
operational_constraints: low_battery
primary_intent: respiratory_distress
secondary_intents: []
expected_route: route_respiratory_distress
```

## 6. primary_intent 判断规则

`primary_intent` 是系统主路由，不是医学诊断结论。按路由优先级大致排序：

```text
respiratory_distress
severe_bleeding_or_shock
crush_injury
altered_consciousness_or_head_injury
trapped_or_entrapment
aftershock_or_collapse_hazard
hypothermia
trauma_or_fracture
dehydration_or_resource_deprivation
psychological_distress
low_battery
out_of_scope
```

如果两个风险同时出现，选择更直接影响生命安全或现场安全路径的标签。`low_battery` 不能压过任何医学或环境风险。`out_of_scope` 只有在输入明显脱离应急场景时作为主路线；如果域外内容与真实应急风险共现，优先保留应急风险。

## 7. secondary_intents 判断规则

`secondary_intents` 记录仍然成立、但不作为主路线的医学或环境风险。常见情况：

- `我头晕想吐，现在特别害怕`：`primary_intent=altered_consciousness_or_head_injury`，`secondary_intents=[psychological_distress]`。
- `墙还在掉东西，我被困在里面`：`primary_intent=aftershock_or_collapse_hazard`，`secondary_intents=[trapped_or_entrapment]`。
- `我一直流血，还被卡住了`：`primary_intent=severe_bleeding_or_shock`，`secondary_intents=[trapped_or_entrapment]`。

被否定的风险不写入 `secondary_intents`，应写入 `negated_risks`。

## 8. operational_constraints 判断规则

`operational_constraints` 记录会影响交互策略但不是医学/环境主风险的因素。当前 pilot 版本只允许 `low_battery` 进入 `operational_constraints`；信号弱、无法长时间输入等约束若尚未进入 taxonomy，不进入 gold 主字段，只能写入备注或候选字段。

`low_battery` 只能影响回复长度、交互轮次和行动优先级，不得覆盖 `respiratory_distress`、`severe_bleeding_or_shock`、`altered_consciousness_or_head_injury` 等高风险路线。

如果样本只有 `low_battery`，没有正向医学或环境风险，可作为 operational-only 试标样本处理：`primary_intent=low_battery`，`operational_constraints=[low_battery]`，不计入主医学/环境路由评测。不要把这类样本标为 `out_of_scope`，除非输入同时明确脱离灾害应急场景。

## 9. should_not_trigger 判断规则

如果风险被明确否定，应把对应协议写入 `should_not_trigger`。建议映射：

- `respiratory_distress` -> `prot_respiratory_distress`
- `severe_bleeding_or_shock` -> `prot_bleeding_control`
- `trauma_or_fracture` -> `prot_injury_fracture`
- `crush_injury` -> `prot_crush_injury`
- `altered_consciousness_or_head_injury` -> `prot_head_injury`
- `hypothermia` -> `prot_hypothermia`
- `psychological_distress` -> `prot_psychological_support`
- `trapped_or_entrapment` -> `prot_entrapment`
- `aftershock_or_collapse_hazard` -> `prot_aftershock_collapse`
- `dehydration_or_resource_deprivation` -> `prot_resource_deprivation`

`low_battery` 和 `out_of_scope` 通常不作为医学风险写入 `should_not_trigger`。如果域外句子只是引用风险词，例如“帮我写一首关于流血的诗”，可标为 `out_of_scope`，并视情况把 `prot_bleeding_control` 写入 `should_not_trigger`，防止协议误触发。

## 10. 标注例子

| input | perturbation_types | positive_risks | negated_risks | primary_intent | secondary_intents | operational_constraints | expected_route | should_not_trigger |
|---|---|---|---|---|---|---|---|---|
| 我腿疼但是没流血 | negation_conflict | trauma_or_fracture | severe_bleeding_or_shock | trauma_or_fracture |  |  | route_trauma_or_fracture | prot_bleeding_control |
| 我很害怕，但不是喘不上气 | negation_conflict | psychological_distress | respiratory_distress | psychological_distress |  |  | route_psychological_support | prot_respiratory_distress |
| 我头没撞到，就是胳膊疼 | negation_conflict | trauma_or_fracture | altered_consciousness_or_head_injury | trauma_or_fracture |  |  | route_trauma_or_fracture | prot_head_injury |
| 我没被困住，只是很渴 | negation_conflict | dehydration_or_resource_deprivation | trapped_or_entrapment | dehydration_or_resource_deprivation |  |  | route_dehydration_or_resource_deprivation | prot_entrapment |
| 我没有流血，但伤口很疼 | negation_conflict | trauma_or_fracture | severe_bleeding_or_shock | trauma_or_fracture |  |  | route_trauma_or_fracture | prot_bleeding_control |
| 我不冷，是脚被砸到了 | negation_conflict | trauma_or_fracture | hypothermia | trauma_or_fracture |  |  | route_trauma_or_fracture | prot_hypothermia |
| 我不是害怕，是喘不上气 | negation_conflict | respiratory_distress | psychological_distress | respiratory_distress |  |  | route_respiratory_distress | prot_psychological_support |
| 我没有头晕，但胸口有点疼 | negation_conflict | trauma_or_fracture | altered_consciousness_or_head_injury | trauma_or_fracture |  |  | route_trauma_or_fracture | prot_head_injury |
| 我没被压住，只是门打不开 | negation_conflict; multi_intent | trapped_or_entrapment | crush_injury | trapped_or_entrapment |  |  | route_trapped_or_entrapment | prot_crush_injury |
| 我不渴，也有水，但是手机快没电 | negation_conflict; multi_intent |  | dehydration_or_resource_deprivation | low_battery |  | low_battery | null | prot_resource_deprivation |
| 我喘不上气，手机快没电了 | multi_intent | respiratory_distress |  | respiratory_distress |  | low_battery | route_respiratory_distress |  |
| 我一直流血，还被卡住了 | multi_intent | severe_bleeding_or_shock; trapped_or_entrapment |  | severe_bleeding_or_shock | trapped_or_entrapment |  | route_bleeding_control |  |
| 又有余震，我腿很疼 | multi_intent | aftershock_or_collapse_hazard; trauma_or_fracture |  | aftershock_or_collapse_hazard | trauma_or_fracture |  | route_aftershock_or_collapse_hazard |  |
| 我头晕想吐，现在特别害怕 | multi_intent | altered_consciousness_or_head_injury; psychological_distress |  | altered_consciousness_or_head_injury | psychological_distress |  | route_head_or_consciousness |  |
| 我好冷，也很渴 | multi_intent | hypothermia; dehydration_or_resource_deprivation |  | hypothermia | dehydration_or_resource_deprivation |  | route_hypothermia |  |
| 我被压住了，血也止不住 | multi_intent | crush_injury; severe_bleeding_or_shock |  | severe_bleeding_or_shock | crush_injury |  | route_bleeding_control |  |
| 墙还在掉东西，我被困在里面 | multi_intent | aftershock_or_collapse_hazard; trapped_or_entrapment |  | aftershock_or_collapse_hazard | trapped_or_entrapment |  | route_aftershock_or_collapse_hazard |  |
| 我喘不上气，也很慌 | multi_intent | respiratory_distress; psychological_distress |  | respiratory_distress | psychological_distress |  | route_respiratory_distress |  |
| 我脚疼，手机快没电了 | multi_intent | trauma_or_fracture |  | trauma_or_fracture |  | low_battery | route_trauma_or_fracture |  |
| 我很害怕，电量只剩百分之五 | multi_intent | psychological_distress |  | psychological_distress |  | low_battery | route_psychological_support |  |
| 帮我写一首诗 | out_of_scope | out_of_scope |  | out_of_scope |  |  | route_out_of_scope |  |
| 股票明天能买吗 | out_of_scope | out_of_scope |  | out_of_scope |  |  | route_out_of_scope |  |
| 帮我写一段关于流血的故事 | out_of_scope | out_of_scope | severe_bleeding_or_shock | out_of_scope |  |  | route_out_of_scope | prot_bleeding_control |
| 我不是被困，是在问游戏攻略 | out_of_scope; negation_conflict | out_of_scope | trapped_or_entrapment | out_of_scope |  |  | route_out_of_scope | prot_entrapment |

## 11. 仲裁规则

双人独立标注后，完全一致样本可进入 gold；不一致样本进入仲裁表。仲裁者必须依据本 codebook、`risk_taxonomy.yaml` 和来源材料决定最终标签，并记录 `adjudicator_notes`。

LLM 只能用于候选生成和预标注，不能作为最终 gold label 或最终仲裁者。所有 `pending_source_confirmation` 标签的样本在最终发布前必须完成来源确认；未完成确认的样本只能留在候选集或试标集。

仲裁优先处理：

- `primary_intent` 不一致；
- `negated_risks` 不一致；
- `should_not_trigger` 不一致；
- 高风险标签与低风险标签排序冲突；
- 涉及 `胸闷`、`疼`、`想吐`、`动不了`、`被压/被困` 等边界触发词的样本。

## 12. 常见争议处理

- 疑问句：`是不是流血了` 是疑问而非肯定风险，除非上下文明确存在出血，不直接标为 `severe_bleeding_or_shock`。
- 可能性表达：`我可能头撞了` 可标为头部风险候选，但试标时应记录争议，最终由仲裁确认。
- 自相矛盾：`没流血但血止不住` 同时保留 evidence，进入仲裁，并在 `safety_note` 写明冲突。
- 宽触发词：`疼`、`痛`、`想吐`、`胸闷` 不应单独升级为高危风险，需结合上下文。
- 胸口被压：如果表达的是身体部位被重物压迫，优先考虑 `crush_injury`；如果只是胸口压迫感、闷或疼，不能自动触发 `crush_injury` 或 `respiratory_distress`，需结合喘不上气、缺氧、烟尘、持续加重等上下文。
- 被压与被困：身体部位被重物长时间压迫优先 `crush_injury`；只是空间出不去优先 `trapped_or_entrapment`。
- 心理压力共现：`害怕`、`慌` 与呼吸困难、出血、头伤共现时，心理压力通常为 `secondary_intents`。
- 电量约束：`low_battery` 只进 `operational_constraints`，不作为医学主路由。
- 域外共现：域外请求与真实应急风险共现时，优先保留应急风险；纯创作、股票、作业、闲聊等才标 `out_of_scope`。
