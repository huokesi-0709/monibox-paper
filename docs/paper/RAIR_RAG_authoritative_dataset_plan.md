# RAIR-RAG 权威依据驱动数据集构建与仓库改造方案

> 建议文件位置：`docs/paper/rair_rag_authoritative_dataset_plan.md`  
> 建议数据集名称：`MoniRisk-Routing-Bench` 或 `RAIR-RAG-Bench`  
> 建议论文主题：**面向离线灾害应急 RAG 的风险感知输入鲁棒化方法：否定冲突消解与多意图优先级路由**

---

## 0. 本方案要解决什么问题

当前论文不要再把“输入鲁棒、协议门控、安全重排、低证据退化、DE 优化”全部平铺成多个并列创新。新的核心应收束为：

> 离线灾害应急 RAG 在进入检索和协议路由前，容易因为用户输入中的语义扰动而误解风险上下文。本文聚焦两类最影响安全路径选择的语义扰动：**否定冲突**和**多意图输入**。前者会导致协议误触发，后者会导致高风险意图漏检。本文构建一个基于权威急救/应急指南的数据集，并提出风险感知输入路由方法，在 RAG 检索前生成修正风险上下文。

这意味着本文优化的不是底层向量检索算法，不是 embedding 模型，也不是向量数据库索引，而是：

```text
原始输入 x
  -> 否定冲突消解
  -> 多意图抽取与风险优先级路由
  -> 修正风险上下文 r*
  -> 协议门控 / RAG 检索 / 安全回复
```

本文改进的 RAG 步骤是：

```text
RAG 前的 Query Understanding / Risk Context Construction / Routing
```

也就是让 RAG 和协议系统拿到更可靠的风险语义上下文。

---

## 1. 数据集建设总目标

### 1.1 数据集名称建议

建议命名为：

```text
MoniRisk-Routing-Bench
```

或者更贴合论文：

```text
RAIR-RAG-Bench
Risk-Aware Input Routing Benchmark for Offline RAG-Based Disaster Emergency Response
```

中文：

```text
面向离线灾害应急 RAG 的风险感知输入路由基准集
```

### 1.2 数据集性质

它不是“官方直接发布的数据集”。目前没有现成公开数据集同时满足：

- 灾害受困场景；
- 受困者第一人称输入；
- 否定冲突；
- 多意图风险表达；
- 风险主次意图标注；
- 期望协议路由；
- RAG 前风险上下文标签；
- 中文/中英混合表达；
- 官方急救/应急依据映射。

因此本数据集应定位为：

> **权威指南依据驱动的人工标注基准集**。

它的权威性来自四点：

1. 风险标签体系来自 WHO/ICRC、WHO PFA、中文应急/地震自救材料等权威来源；
2. 每个风险标签都要映射到指南条款或应急科普依据；
3. 样本标注采用明确 codebook、双人独立标注和仲裁；
4. 训练/开发/测试划分严格防止泄漏，DE 只能在 dev split 上调参。

---

## 2. 必须查阅或下载的权威资料

### 2.1 WHO-ICRC Basic Emergency Care

用途：支撑医学急救风险标签，例如呼吸困难、严重出血、休克、创伤、意识异常、失温等。

官方页面：

```text
https://www.who.int/publications/i/item/9789241513081
```

页面中可下载主手册：

```text
https://iris.who.int/server/api/core/bitstreams/63432b9f-8808-44c5-9692-cea717c0cbda/content
```

页面中可下载 Quick Cards：

```text
https://cdn.who.int/media/docs/default-source/integrated-health-services-%28ihs%29/csy/bec-quick-cards/becp-edu29-pdf-en-finl.pdf?sfvrsn=2532d61b_4
```

重点查阅章节/卡片：

```text
ABCDE approach
Airway
Breathing
Circulation
Disability
Exposure
Trauma
Shock
Altered mental status
```

可映射到本数据集的风险标签：

| WHO/BEC 内容 | 数据集风险标签 |
|---|---|
| Airway / Breathing / abnormal breathing / hypoxia | respiratory_distress |
| Internal or external bleeding / shock | severe_bleeding_or_shock |
| Trauma / fracture / crush injury | trauma_or_fracture / crush_injury |
| Altered mental status / brain injury | altered_consciousness_or_head_injury |
| Exposure / prevent hypothermia | hypothermia |

注意：WHO BEC 是给 first-contact healthcare providers 使用的，不是普通受困者自救手册。因此数据集只把它作为“风险识别依据”，不能把专业医疗操作原样变成用户输出，例如 needle decompression、IV fluids、tourniquet 等不能直接输出给普通受困者。

---

### 2.2 WHO Psychological First Aid

用途：支撑心理压力、恐慌、危机安抚类标签。

官方页面：

```text
https://www.who.int/publications/i/item/9789241548205
```

下载地址：

```text
https://iris.who.int/server/api/core/bitstreams/e7e129fb-b306-496d-84a5-67bb70abc130/content
```

建议用于映射：

```text
panic / psychological_distress
```

注意：PFA 支撑的是危机后的支持性、实用性帮助，不是“心理治疗”。论文里应写成：

```text
psychological distress route is designed for stabilization and supportive interaction, not diagnosis or therapy.
```

---

### 2.3 中国应急管理部资料

用途：支撑中文灾害应急、地震、自然灾害、应急科普等材料。

官方网站：

```text
https://www.mem.gov.cn/
```

重点入口：

```text
https://www.mem.gov.cn/kp/
https://www.mem.gov.cn/kp/zrzh/
```

页面栏目建议人工检索：

```text
应急科普
自然灾害
地震
防震减灾
地震避险
地震自救
被困自救
```

建议检索关键词：

```text
地震 被困 自救
被埋压 保存体力 敲击 求救
余震 坍塌 避险
地震 受伤 自救
```

说明：

- 如果能找到应急管理部或其转载的官方科普文章，应优先使用；
- 如果只找到媒体转载，需要记录原始来源；
- 不能把非官方自媒体文章作为核心指南依据。

---

### 2.4 中国地震局资料

用途：支撑地震避险、震后自救、被困求救、余震/坍塌环境风险。

官方网站：

```text
http://www.cea.gov.cn/
```

建议人工检索关键词：

```text
地震自救
震后自救
被埋压 自救
防震减灾 科普
地震避险 自救互救
```

说明：

- 中国地震局资料更适合支撑 `aftershock_or_collapse_hazard`、`trapped_or_entrapment`、`earthquake_scene`；
- 若无法找到完整自救手册，可使用地方地震局、地震科普馆、地震灾害防御中心的官方材料，但要记录来源层级。

---

### 2.5 国家应急广播资料

用途：支撑灾害现场面向公众的应急科普语言，尤其适合把专业指南转写成受困者可理解的短句。

官方网站：

```text
https://www.cneb.gov.cn/
```

建议人工检索关键词：

```text
地震 自救
被困 求救
保存体力
敲击 求救
余震 避险
```

说明：

- 国家应急广播的科普表达通常比医学指南更接近普通用户语言；
- 可作为 `reference_reply` 和 `safety_note` 的语言风格参考。

---

### 2.6 中国红十字会资料

用途：支撑公众急救、自救互救、出血压迫、骨折固定、心理支持等普通人可执行动作边界。

官方网站：

```text
https://www.redcross.org.cn/
```

建议人工检索关键词：

```text
急救 出血 按压
创伤 急救
骨折 固定
地震 自救互救
应急救护
```

说明：

- 中国红十字会材料更适合把 WHO/BEC 的医疗风险转换成普通人可执行的安全动作；
- 例如严重出血可支撑“直接按压伤口”这类低风险动作，但不应引导普通用户执行专业操作。

---

### 2.7 参考型灾害 NLP 数据集

这些数据集不是本文直接使用的数据，但可以用于写“相关工作”和“数据构建参考”。

CrisisBench：

```text
https://arxiv.org/abs/2004.06774
https://crisisnlp.qcri.org/crisis_datasets_benchmarks.html
```

HumAID：

```text
https://arxiv.org/abs/2104.03090
https://crisisnlp.qcri.org/humaid_dataset.html
```

它们的价值：

- 证明灾害 NLP 数据集通常需要人工标注；
- 证明灾害文本分类已有研究基础；
- 说明已有数据集多面向社交媒体信息分类，而不是受困者输入风险路由。

---

### 2.8 否定检测与多意图识别参考文献

否定检测：

```text
NegBio: a high-performance tool for negation and uncertainty detection in radiology reports
https://arxiv.org/abs/1712.05898
```

多意图识别：

```text
DialogUSR: Complex Dialogue Utterance Splitting and Reformulation for Multiple Intent Detection
https://arxiv.org/abs/2210.11279
```

这些文献的作用：

- 证明“否定冲突”和“多意图输入”不是随便想出来的问题，而是 NLP 中有正式研究背景的问题；
- 但论文不能声称“首次提出否定检测”或“首次提出多意图识别”；
- 本文创新应写成“把这两类语义扰动引入离线灾害应急 RAG 的检索前风险路由阶段”。

---

## 3. 数据集标签体系设计

### 3.1 风险标签不要再笼统写 11 类医学意图

建议拆成三层：

#### A 类：医学急救风险

```text
respiratory_distress
severe_bleeding_or_shock
trauma_or_fracture
crush_injury
altered_consciousness_or_head_injury
hypothermia
psychological_distress
```

#### B 类：灾害受困环境风险

```text
trapped_or_entrapment
aftershock_or_collapse_hazard
dehydration_or_resource_deprivation
```

#### C 类：系统边界与运行约束

```text
low_battery
out_of_scope
```

注意：

- `low_battery` 不是医学风险，应作为 operational constraint；
- `out_of_scope` 不是急救风险，应作为 safety boundary route；
- `pain_or_injury` 建议改成 `trauma_or_fracture` 或 `musculoskeletal_injury`，因为“疼痛”本身太泛。

---

### 3.2 主要扰动类型

论文引言可以列出七类扰动：

| 层级 | 扰动类型 | 论文地位 |
|---|---|---|
| 信号层 | ASR 同音错 | 背景 + 预处理 |
| 信号层 | 呼吸类错听 | 背景 + 预处理 |
| 信号层 | 口语噪声 | 背景 + 预处理 |
| 信号层 | 重复表达 | 背景 + 预处理 |
| 语义层 | 否定冲突 | 核心研究对象 |
| 语义层 | 多意图输入 | 核心研究对象 |
| 边界层 | 域外输入 | 边界控制，补充实验 |

论文主实验只围绕：

```text
negation_conflict
multi_intent
```

其他扰动保留为背景和补充实验，不写成主贡献。

---

## 4. 数据字段设计

建议新增一种专门用于 RAIR-RAG 的 JSONL schema，不要强行塞进现有 `BenchmarkCase`。现有 schema 可以保留兼容，但新数据集需要更多字段。

建议文件：

```text
benchmarks/routing_schema.py
```

单条样本字段：

```json
{
  "id": "neg_0001",
  "canonical_id": "case_bleeding_neg_0001",
  "raw_input": "我腿疼但是没流血",
  "canonical_input": "我腿疼，但是没有流血",
  "language": "zh-CN",
  "source_type": "template_generated_human_reviewed",
  "guideline_refs": [
    {
      "source_id": "WHO_BEC_2018",
      "section": "Circulation / external bleeding",
      "risk_mapping": "severe_bleeding_or_shock"
    }
  ],
  "perturbation_types": ["negation_conflict"],
  "risk_mentions": ["pain", "bleeding"],
  "positive_risks": ["trauma_or_fracture"],
  "negated_risks": ["severe_bleeding_or_shock"],
  "primary_intent": "trauma_or_fracture",
  "secondary_intents": [],
  "operational_constraints": [],
  "expected_route": "route_trauma_or_fracture",
  "expected_protocol_id": "prot_injury_fracture",
  "should_not_trigger": ["prot_bleeding_control"],
  "risk_level": "medium",
  "expected_tags": ["risk_injury", "body:腿"],
  "safety_note": "被否定的出血风险不应触发严重出血协议。",
  "reference_reply": "先别硬动疼的地方。疼的地方有没有发麻、变形？",
  "label_status": "adjudicated"
}
```

---

## 5. 数据集规模建议

### 5.1 最低可投稿规模

```text
总量：600-800 条
否定冲突：150 条
多意图输入：200 条
普通 clean 对照：150-200 条
信号层扰动补充：100-150 条
域外/边界样本：80-100 条
```

### 5.2 更稳规模

```text
总量：1000-1200 条
否定冲突：250 条
多意图输入：300 条
普通 clean 对照：250 条
信号层扰动补充：200 条
域外/边界样本：100-150 条
```

### 5.3 为什么不继续追求 6000 条

当前新主题更关注标注质量，而不是样本规模。一个 800 条高质量、权威依据清楚、双人标注、仲裁完整的数据集，比一个泛化构造但标注弱的 6000 条数据集更适合支撑这篇论文。

---

## 6. 数据构建流程

### Step 1：建立 `guideline_sources.yaml`

建议文件：

```text
benchmarks/rair_rag/sources/guideline_sources.yaml
```

内容示例：

```yaml
- source_id: WHO_BEC_2018
  title: "WHO-ICRC Basic Emergency Care: approach to the acutely ill and injured"
  organization: "WHO / ICRC"
  year: 2018
  url: "https://www.who.int/publications/i/item/9789241513081"
  download_url: "https://iris.who.int/server/api/core/bitstreams/63432b9f-8808-44c5-9692-cea717c0cbda/content"
  local_path: "benchmarks/rair_rag/sources/raw/WHO_BEC_2018.pdf"
  used_for:
    - respiratory_distress
    - severe_bleeding_or_shock
    - trauma_or_fracture
    - crush_injury
    - altered_consciousness_or_head_injury
    - hypothermia

- source_id: WHO_PFA_2011
  title: "Psychological first aid: Guide for field workers"
  organization: "WHO"
  year: 2011
  url: "https://www.who.int/publications/i/item/9789241548205"
  download_url: "https://iris.who.int/server/api/core/bitstreams/e7e129fb-b306-496d-84a5-67bb70abc130/content"
  local_path: "benchmarks/rair_rag/sources/raw/WHO_PFA_2011.pdf"
  used_for:
    - psychological_distress
```

人工工作：

- 打开资料页面；
- 下载 PDF；
- 记录来源、年份、机构、URL；
- 标明每份资料支持哪些风险标签。

Codex 提示词：

```text
你现在在 monibox-paper 仓库中工作。请创建 benchmarks/rair_rag/sources/guideline_sources.yaml，用于记录权威指南来源。
要求：
1. 创建目录 benchmarks/rair_rag/sources/ 和 benchmarks/rair_rag/sources/raw/。
2. 写入 WHO_BEC_2018、WHO_PFA_2011、MEM_CHINA、CEA_CHINA、CNEB_CHINA、REDCROSS_CHINA 六个 source 条目。
3. 每个条目包含 source_id、title、organization、year、url、download_url、local_path、used_for、notes 字段。
4. 对于暂未确认具体 PDF 的中文来源，download_url 写 null，notes 写“待人工检索确认具体材料”。
5. 不要下载文件，只创建 YAML。
6. 保持 UTF-8 编码。
```

---

### Step 2：建立风险标签映射表

建议文件：

```text
benchmarks/rair_rag/annotation/risk_taxonomy.yaml
```

内容示例：

```yaml
risk_labels:
  respiratory_distress:
    category: medical_life_threatening
    priority: 1.00
    guideline_basis:
      - source_id: WHO_BEC_2018
        section: "Airway / Breathing"
    positive_triggers:
      - 喘不上气
      - 呼吸困难
      - 吸不上气
      - 窒息
    negatable: true
    default_route: route_respiratory_distress

  severe_bleeding_or_shock:
    category: medical_life_threatening
    priority: 0.95
    guideline_basis:
      - source_id: WHO_BEC_2018
        section: "Circulation / bleeding / shock"
    positive_triggers:
      - 流血
      - 出血
      - 血止不住
      - 很多血
    negatable: true
    default_route: route_bleeding_control

  low_battery:
    category: operational_constraint
    priority: 0.20
    guideline_basis: []
    positive_triggers:
      - 手机没电
      - 快没电
      - 电量低
    negatable: false
    default_route: null
```

人工工作：

- 把 WHO/BEC、PFA、中文自救材料中的风险条款映射到系统标签；
- 决定每个标签的优先级；
- 决定哪些风险可以被否定；
- 决定哪些标签只作为次要约束。

Codex 提示词：

```text
请在 monibox-paper 仓库中创建 benchmarks/rair_rag/annotation/risk_taxonomy.yaml。
要求：
1. 使用 YAML 定义 risk_labels。
2. 包含以下标签：respiratory_distress、severe_bleeding_or_shock、trauma_or_fracture、crush_injury、altered_consciousness_or_head_injury、hypothermia、psychological_distress、trapped_or_entrapment、aftershock_or_collapse_hazard、dehydration_or_resource_deprivation、low_battery、out_of_scope。
3. 每个标签包含 category、priority、guideline_basis、positive_triggers、negatable、default_route、notes。
4. category 只能从 medical_life_threatening、medical_non_life_threatening、environmental_hazard、operational_constraint、safety_boundary 中选择。
5. 明确 low_battery 是 operational_constraint，不是医学风险。
6. 明确 out_of_scope 是 safety_boundary，不是医学风险。
7. 不要修改 runtime/intent_extractor.py。
```

---

### Step 3：写标注指南 Codebook

建议文件：

```text
benchmarks/rair_rag/annotation/annotation_codebook.md
```

必须包括：

```text
1. 标注目标
2. 标签来源
3. 风险标签定义
4. 否定冲突定义
5. 多意图输入定义
6. primary_intent 判断规则
7. secondary_intents 判断规则
8. operational_constraints 判断规则
9. should_not_trigger 判断规则
10. 标注例子
11. 仲裁规则
12. 常见争议处理
```

否定冲突判定例：

```text
句子：我腿疼但是没流血
risk_mentions: pain, bleeding
positive_risks: trauma_or_fracture
negated_risks: severe_bleeding_or_shock
primary_intent: trauma_or_fracture
should_not_trigger: prot_bleeding_control
```

多意图判定例：

```text
句子：我喘不上气，手机快没电了
positive_risks: respiratory_distress
operational_constraints: low_battery
primary_intent: respiratory_distress
secondary_intents: []
expected_route: route_respiratory_distress
```

人工工作：

- 写清楚每个标签怎么标；
- 组织标注者培训；
- 对 20-50 条样本试标；
- 根据不一致情况修订 codebook。

Codex 提示词：

```text
请创建 benchmarks/rair_rag/annotation/annotation_codebook.md，内容为 RAIR-RAG-Bench 的人工标注指南。
要求：
1. 用中文撰写。
2. 明确本文只把 negation_conflict 和 multi_intent 作为核心语义扰动。
3. 其他五类扰动作为背景/预处理标签，不作为主贡献。
4. 给出不少于 20 条标注示例，其中 negation_conflict 至少 8 条，multi_intent 至少 8 条，out_of_scope 至少 2 条，low_battery 作为次要约束至少 2 条。
5. 明确 primary_intent、secondary_intents、positive_risks、negated_risks、operational_constraints、should_not_trigger 的判定规则。
6. 明确争议样本需要人工仲裁，LLM 只能用于候选生成和预标注，不能作为最终 gold label。
7. 不要修改代码。
```

---

### Step 4：建立样本模板文件

建议文件：

```text
benchmarks/rair_rag/templates/negation_templates.yaml
benchmarks/rair_rag/templates/multi_intent_templates.yaml
benchmarks/rair_rag/templates/control_templates.yaml
```

否定模板示例：

```yaml
- template_id: neg_bleeding_pain_001
  pattern: "我{body_part}疼，但是没{bleeding_term}"
  positive_risks:
    - trauma_or_fracture
  negated_risks:
    - severe_bleeding_or_shock
  should_not_trigger:
    - prot_bleeding_control
  slots:
    body_part: [腿, 胳膊, 手, 脚]
    bleeding_term: [流血, 出血]
```

多意图模板示例：

```yaml
- template_id: multi_resp_battery_001
  pattern: "我{resp_term}，手机也{battery_term}"
  positive_risks:
    - respiratory_distress
  operational_constraints:
    - low_battery
  primary_intent: respiratory_distress
  slots:
    resp_term: [喘不上气, 呼吸困难, 吸不上气]
    battery_term: [快没电了, 电量很低, 快关机了]
```

人工工作：

- 设计模板；
- 检查模板是否过度机械化；
- 每个模板生成后要人工筛选语言自然度。

Codex 提示词：

```text
请创建 benchmarks/rair_rag/templates/negation_templates.yaml、multi_intent_templates.yaml、control_templates.yaml。
要求：
1. negation_templates.yaml 至少包含 30 个模板，覆盖 bleeding、respiratory_distress、head injury、hypothermia、dehydration、crush injury 的否定表达。
2. multi_intent_templates.yaml 至少包含 40 个模板，覆盖 respiratory+low_battery、bleeding+panic、crush+respiratory、hypothermia+trapped、head+bleeding 等组合。
3. control_templates.yaml 至少包含 20 个普通 clean 对照模板。
4. 每个模板包含 template_id、pattern、slots、positive_risks、negated_risks、operational_constraints、primary_intent、secondary_intents、should_not_trigger、notes。
5. 不生成最终 JSONL 数据，只创建模板文件。
```

---

### Step 5：生成候选样本

建议脚本：

```text
benchmarks/rair_rag/scripts/generate_candidates.py
```

输出：

```text
benchmarks/rair_rag/data/candidates/rair_candidates.jsonl
```

功能：

- 读取模板；
- 展开 slots；
- 生成 raw_input；
- 自动带上模板内的标签；
- 标记 source_type 为 `template_generated`；
- 每条样本加 `needs_human_review: true`。

Codex 提示词：

```text
请新增 benchmarks/rair_rag/scripts/generate_candidates.py。
要求：
1. 从 benchmarks/rair_rag/templates/*.yaml 读取模板。
2. 展开 slots 生成候选样本。
3. 输出 JSONL 到 benchmarks/rair_rag/data/candidates/rair_candidates.jsonl。
4. 每条样本包含 id、canonical_id、raw_input、canonical_input、source_type、perturbation_types、positive_risks、negated_risks、operational_constraints、primary_intent、secondary_intents、should_not_trigger、expected_route、expected_protocol_id、risk_level、expected_tags、label_status、needs_human_review。
5. id 前缀按扰动类型生成，例如 neg_0001、multi_0001、clean_0001、boundary_0001。
6. 脚本只使用标准库和 pyyaml。
7. 增加 argparse 参数 --out。
8. 不修改现有 benchmarks/run_eval.py。
```

---

### Step 6：人工筛选和改写候选样本

候选样本不能直接作为 gold label。必须做人工筛选。

建议流程：

```text
1. 将 rair_candidates.jsonl 导出为 CSV。
2. 两名人工分别检查 raw_input 是否自然、标签是否合理。
3. 删除机械化、重复、语义不清、危险表达不合理的样本。
4. 必要时人工改写 raw_input，使其更像受困者第一人称表达。
5. 保留修订记录。
```

建议文件：

```text
benchmarks/rair_rag/data/annotation_rounds/round1_for_annotator_A.csv
benchmarks/rair_rag/data/annotation_rounds/round1_for_annotator_B.csv
benchmarks/rair_rag/data/annotation_rounds/round1_merged.csv
```

Codex 提示词：

```text
请新增 benchmarks/rair_rag/scripts/jsonl_to_annotation_csv.py。
要求：
1. 输入 benchmarks/rair_rag/data/candidates/rair_candidates.jsonl。
2. 输出 CSV 到 benchmarks/rair_rag/data/annotation_rounds/round1_for_annotation.csv。
3. CSV 字段包括：id、raw_input、canonical_input、perturbation_types、risk_mentions、positive_risks、negated_risks、operational_constraints、primary_intent、secondary_intents、expected_route、expected_protocol_id、should_not_trigger、risk_level、guideline_refs、human_accept、human_notes、annotator_primary_intent、annotator_negated_risks、annotator_secondary_intents。
4. 列表字段使用 | 拼接，方便 Excel/WPS 编辑。
5. 不要覆盖已有文件，除非传入 --overwrite。
```

---

### Step 7：双人独立标注

标注者 A 和 B 独立填写：

```text
human_accept
annotator_primary_intent
annotator_secondary_intents
annotator_negated_risks
annotator_operational_constraints
annotator_should_not_trigger
annotator_notes
```

人工规则：

- 两人不能互相看结果；
- 先标 50 条试标样本；
- 计算一致性；
- 修订 codebook；
- 再开始正式标注。

Codex 提示词：

```text
请新增 benchmarks/rair_rag/scripts/split_annotation_batches.py。
要求：
1. 读取 round1_for_annotation.csv。
2. 生成 round1_annotator_A.csv 和 round1_annotator_B.csv。
3. 两个文件内容相同，但增加 annotator_id 字段。
4. 支持 --sample-size 参数，用于先抽取 50 条试标样本。
5. 支持 --seed，保证可复现。
6. 不要做任何自动标注，只负责生成标注文件。
```

---

### Step 8：一致性检验

建议脚本：

```text
benchmarks/rair_rag/scripts/compute_agreement.py
```

输出：

```text
benchmarks/rair_rag/reports/agreement_report.md
benchmarks/rair_rag/reports/agreement_metrics.json
```

指标建议：

| 字段 | 指标 |
|---|---|
| perturbation_type | Cohen's kappa |
| primary_intent | Cohen's kappa + macro-F1 |
| negated_risks | set-F1 / exact match |
| secondary_intents | set-F1 / exact match |
| should_not_trigger | set-F1 |

如果有三名以上标注者，再加 Krippendorff's alpha。

Codex 提示词：

```text
请新增 benchmarks/rair_rag/scripts/compute_agreement.py。
要求：
1. 读取两个标注 CSV：--ann-a 和 --ann-b。
2. 对 primary_intent、perturbation_types、negated_risks、secondary_intents、should_not_trigger 计算一致性。
3. 对单标签字段计算 observed agreement 和 Cohen's kappa。
4. 对多标签字段计算 exact_match、micro precision、micro recall、micro F1。
5. 不引入 sklearn，使用标准库实现。
6. 输出 JSON 到 benchmarks/rair_rag/reports/agreement_metrics.json。
7. 输出 Markdown 报告到 benchmarks/rair_rag/reports/agreement_report.md。
8. 报告中列出不一致样本 id，供人工仲裁。
```

---

### Step 9：人工仲裁

建议文件：

```text
benchmarks/rair_rag/data/annotation_rounds/adjudication_sheet.csv
benchmarks/rair_rag/data/gold/rair_gold_all.jsonl
```

仲裁原则：

- 标注者一致的样本可直接进入 gold；
- 不一致样本由仲裁者按 codebook 决定；
- 所有仲裁样本记录 `label_status: adjudicated`；
- 不能用 LLM 作为最终仲裁者。

Codex 提示词：

```text
请新增 benchmarks/rair_rag/scripts/build_adjudication_sheet.py。
要求：
1. 读取 annotator_A.csv、annotator_B.csv 和 agreement_metrics.json 中的不一致样本列表。
2. 输出 adjudication_sheet.csv。
3. 每行同时展示 A 标注、B 标注、原始模板标签，并留出 final_primary_intent、final_negated_risks、final_secondary_intents、final_should_not_trigger、adjudicator_notes 字段。
4. 不自动决定最终标签。
5. 不要删除任何输入文件。
```

Codex 提示词：

```text
请新增 benchmarks/rair_rag/scripts/build_gold_jsonl.py。
要求：
1. 读取人工仲裁后的 adjudication_sheet.csv 和一致样本文件。
2. 输出 benchmarks/rair_rag/data/gold/rair_gold_all.jsonl。
3. 每条样本必须符合 benchmarks/rair_rag/routing_schema.py 中的 RoutingCase schema。
4. 如果缺少 final label，脚本必须报错。
5. 输出同时生成 data/gold/label_distribution.json，统计 perturbation_type、primary_intent、risk_level、source_type 分布。
```

---

### Step 10：划分 dev/test，防止泄漏

建议输出：

```text
benchmarks/rair_rag/data/dev/rair_dev.jsonl
benchmarks/rair_rag/data/test/rair_test.jsonl
benchmarks/rair_rag/data/test/rair_test_negation.jsonl
benchmarks/rair_rag/data/test/rair_test_multi_intent.jsonl
```

关键规则：

- 同一个 `canonical_id` 的所有变体必须在同一个 split；
- DE 只能看 dev；
- test 不能参与模板修正、参数调整、权重选择；
- 如果一个 clean 样本和它的 negation/multi_intent 变体属于同一组，也必须一起划分。

Codex 提示词：

```text
请新增 benchmarks/rair_rag/scripts/split_dev_test.py。
要求：
1. 输入 benchmarks/rair_rag/data/gold/rair_gold_all.jsonl。
2. 按 canonical_id 分组划分 dev/test，禁止同一 canonical_id 出现在两个 split 中。
3. 默认 dev_ratio=0.4，test_ratio=0.6，可通过参数修改。
4. 支持 --seed。
5. 输出 rair_dev.jsonl、rair_test.jsonl。
6. 额外输出 rair_test_negation.jsonl 和 rair_test_multi_intent.jsonl。
7. 生成 split_manifest.json，记录每个 split 的样本数、标签分布、canonical_id 数量。
```

---

## 7. 仓库当前情况与改造方案

当前仓库已有以下可复用基础：

```text
README.md
profiles/paper_eval.yaml
benchmarks/run_eval.py
benchmarks/baselines.py
benchmarks/schema.py
benchmarks/metrics.py
runtime/intent_extractor.py
runtime/input_normalizer.py
runtime/protocol_matcher.py
experiments/de_pymoo_optimize.py
```

当前 README 已经明确仓库论文主链是：

```text
文本输入 -> 协议/路由 -> RAG/低证据分流 -> 安全护栏 -> 输出
```

因此新方向不需要推倒重写，而是把主链进一步收束到：

```text
文本输入 -> 风险感知输入路由 -> 协议/RAG -> 输出
```

### 7.1 新增目录结构

建议新增：

```text
benchmarks/rair_rag/
  annotation/
    annotation_codebook.md
    risk_taxonomy.yaml
  sources/
    guideline_sources.yaml
    raw/
  templates/
    negation_templates.yaml
    multi_intent_templates.yaml
    control_templates.yaml
  data/
    candidates/
    annotation_rounds/
    gold/
    dev/
    test/
  reports/
  scripts/
    generate_candidates.py
    jsonl_to_annotation_csv.py
    split_annotation_batches.py
    compute_agreement.py
    build_adjudication_sheet.py
    build_gold_jsonl.py
    split_dev_test.py
    audit_dataset.py
  routing_schema.py
  routing_metrics.py
  run_routing_eval.py
```

### 7.2 修改 runtime 层

当前 `runtime/intent_extractor.py` 已经包含：

- `INTENT_PRIORITY`
- `INTENT_RISK_SCORE`
- `NEGATION_WORDS`
- `NEGATION_BOUNDARIES`
- `INTENT_TERMS`
- `IntentContext`
- `_is_negated()`
- `_select_primary()`

建议不要直接在这个文件里继续硬堆逻辑，而是新增更聚焦的模块：

```text
runtime/risk_router.py
runtime/negation_resolver.py
runtime/multi_intent_router.py
runtime/routing_policy.py
```

#### `runtime/negation_resolver.py`

职责：

```text
输入：文本、风险词匹配结果、配置参数
输出：positive_risks、negated_risks、negation_trace
```

#### `runtime/multi_intent_router.py`

职责：

```text
输入：候选风险、置信度、基础风险权重、运行约束
输出：primary_intent、secondary_intents、operational_constraints、priority_trace
```

#### `runtime/routing_policy.py`

职责：

```text
加载人工或 DE 生成的路由参数，例如：
- negation_window
- negation_penalty
- boundary_terms
- intent_priority_weights
- confidence_thresholds
- high_risk_boost
```

#### `runtime/risk_router.py`

职责：

```text
把 negation_resolver 和 multi_intent_router 组合起来，形成新的 RiskAwareInputRouter。
```

Codex 提示词：

```text
请在 runtime/ 下新增 risk_router.py、negation_resolver.py、multi_intent_router.py、routing_policy.py。
要求：
1. 不删除 runtime/intent_extractor.py，先保持兼容。
2. negation_resolver.py 定义 NegationResolver 和 NegationConfig，支持 negation_window、negation_words、boundary_terms、negation_penalty。
3. multi_intent_router.py 定义 MultiIntentRouter 和 MultiIntentConfig，支持 intent_base_weights、confidence_threshold、high_risk_boost、operational_constraint_weight。
4. routing_policy.py 定义 RoutingPolicy，可从 YAML/JSON 加载参数。
5. risk_router.py 定义 RiskAwareInputRouter，输入 raw/canonical text，输出类似 IntentContext 的 RiskRoutingContext。
6. RiskRoutingContext 至少包含 raw_text、canonical_text、risk_mentions、positive_risks、negated_risks、primary_intent、secondary_intents、operational_constraints、risk_score、trace。
7. 保持纯 Python 标准库，不引入新依赖。
8. 添加最小单元测试 tests/test_risk_router.py。
```

---

### 7.3 修改 benchmarks schema

当前 `benchmarks/schema.py` 的字段偏向旧版评测：`query`、`expected_primary_intent`、`expected_protocol_id`、`gold_chunk_ids` 等。新数据集需要更细的字段。

建议新增：

```text
benchmarks/rair_rag/routing_schema.py
```

不要直接破坏旧 `BenchmarkCase`。

Codex 提示词：

```text
请新增 benchmarks/rair_rag/routing_schema.py。
要求：
1. 定义 dataclass RoutingCase。
2. 字段包括：id、canonical_id、raw_input、canonical_input、language、source_type、guideline_refs、perturbation_types、risk_mentions、positive_risks、negated_risks、primary_intent、secondary_intents、operational_constraints、expected_route、expected_protocol_id、should_not_trigger、risk_level、expected_tags、safety_note、reference_reply、label_status。
3. 提供 from_dict、to_dict、validate、load_routing_cases 函数。
4. validate 必须检查 id/raw_input/primary_intent 非空，risk_level 合法，列表字段类型合法。
5. 不修改 benchmarks/schema.py。
```

---

### 7.4 新增 routing metrics

建议文件：

```text
benchmarks/rair_rag/routing_metrics.py
```

核心指标：

| 指标 | 解释 |
|---|---|
| RouteAcc | 主路由是否正确 |
| HRR | high/critical 样本的高风险召回 |
| PFTR | Protocol False Trigger Rate，协议误触发率 |
| NegRiskAcc | 被否定风险识别准确率 |
| NegRiskF1 | 被否定风险集合 F1 |
| PrimaryIntentAcc | 主意图准确率 |
| SecondaryIntentF1 | 次意图集合 F1 |
| ConstraintF1 | 运行约束集合 F1 |

Codex 提示词：

```text
请新增 benchmarks/rair_rag/routing_metrics.py。
要求：
1. 输入 cases: list[RoutingCase] 和 predictions: list[dict]。
2. 实现 RouteAcc、HRR、PFTR、NegRiskExact、NegRiskF1、PrimaryIntentAcc、SecondaryIntentF1、ConstraintF1。
3. PFTR 定义为：预测 protocol_id 命中了 case.should_not_trigger 中任一协议，或预测 primary_intent 属于被 negated_risks 否定的风险。
4. HRR 定义为：risk_level 为 high/critical 的样本中，预测 primary_intent 等于 gold primary_intent，或者预测 primary_intent 属于 gold positive_risks 中 high-risk 集合。
5. 支持按 perturbation_type 分组输出指标。
6. 不依赖 sklearn。
```

---

### 7.5 新增 routing eval 入口

建议文件：

```text
benchmarks/rair_rag/run_routing_eval.py
```

命令示例：

```bash
uv run python -m benchmarks.rair_rag.run_routing_eval \
  --data benchmarks/rair_rag/data/test/rair_test.jsonl \
  --method risk-router \
  --policy scoring/routing_policy_manual.yaml \
  --out build/rair_eval/test_predictions.jsonl \
  --summary build/rair_eval/test_summary.json
```

Codex 提示词：

```text
请新增 benchmarks/rair_rag/run_routing_eval.py。
要求：
1. 读取 RoutingCase JSONL。
2. 支持 method：keyword-baseline、no-negation、single-intent、risk-router、risk-router-de。
3. keyword-baseline：只按关键词命中选择第一个风险。
4. no-negation：不识别否定。
5. single-intent：识别多个候选后只按置信度最高选择，不使用风险优先级。
6. risk-router：使用 RiskAwareInputRouter 和 manual policy。
7. risk-router-de：使用 DE 生成的 routing policy。
8. 输出 predictions JSONL 和 summary JSON。
9. 调用 routing_metrics.py 计算整体和分扰动指标。
10. 不调用 LLM，不调用远端 API。
```

---

## 8. DE 在新框架里的位置

### 8.1 DE 优化什么

DE 不优化 RAG 检索算法。DE 优化的是：

```text
风险路由参数
```

具体包括：

| 模块 | 参数 |
|---|---|
| 否定冲突 | negation_window |
| 否定冲突 | negation_penalty |
| 否定冲突 | boundary_strength |
| 多意图 | intent_base_weights |
| 多意图 | confidence_threshold |
| 多意图 | high_risk_boost |
| 多意图 | operational_constraint_weight |

### 8.2 DE 目标函数

建议目标函数：

```text
J = 0.35 * RouteAcc
  + 0.30 * HRR
  + 0.15 * NegRiskF1
  + 0.10 * SecondaryIntentF1
  - 0.25 * PFTR
```

约束：

```text
PFTR <= 0.05
HRR >= 0.85
```

注意：这些目标只能在 dev split 上计算。

### 8.3 输出文件

建议：

```text
scoring/routing_policy_manual.yaml
scoring/routing_policy_de.yaml
experiments/configs/de_routing.yaml
experiments/de_routing_optimize.py
build/rair_eval/de_trials.jsonl
build/rair_eval/de_best_policy.yaml
```

Codex 提示词：

```text
请新增 experiments/de_routing_optimize.py 和 experiments/configs/de_routing.yaml。
要求：
1. 使用 pymoo 的 Differential Evolution，如果 pymoo 不可用则报错提示安装 uv sync --extra paper。
2. 只读取 benchmarks/rair_rag/data/dev/rair_dev.jsonl。
3. 优化 RoutingPolicy 参数，包括 negation_window、negation_penalty、confidence_threshold、high_risk_boost、operational_constraint_weight，以及每个 intent 的 base weight。
4. 每个 candidate policy 写入临时 YAML 后调用 run_routing_eval 的内部函数评估。
5. fitness 按 J = 0.35 RouteAcc + 0.30 HRR + 0.15 NegRiskF1 + 0.10 SecondaryIntentF1 - 0.25 PFTR。
6. 输出 scoring/routing_policy_de.yaml、build/rair_eval/de_trials.jsonl、build/rair_eval/de_summary.json。
7. 不使用 test split。
```

---

## 9. 实验设计

### 9.1 主实验

数据：

```text
benchmarks/rair_rag/data/test/rair_test.jsonl
```

方法：

```text
keyword-baseline
no-negation
single-intent
risk-router-manual
risk-router-de
```

重点比较：

| 对比 | 证明什么 |
|---|---|
| keyword-baseline vs no-negation | 关键词匹配不足 |
| no-negation vs risk-router | 否定冲突消解价值 |
| single-intent vs risk-router | 多意图优先级价值 |
| risk-router-manual vs risk-router-de | DE 是否有参数校准价值 |

### 9.2 分扰动实验

```text
rair_test_negation.jsonl
rair_test_multi_intent.jsonl
```

否定冲突重点指标：

```text
PFTR
NegRiskF1
RouteAcc
```

多意图重点指标：

```text
HRR
PrimaryIntentAcc
SecondaryIntentF1
RouteAcc
```

### 9.3 消融实验

```text
w/o negation scope
w/o boundary terms
w/o risk priority
w/o operational constraints
w/o DE calibration
```

Codex 提示词：

```text
请新增 scripts/run_rair_eval.sh。
要求：
1. 依次运行 rair_test、rair_test_negation、rair_test_multi_intent。
2. 每个数据集运行 keyword-baseline、no-negation、single-intent、risk-router、risk-router-de 五种方法。
3. 输出到 build/rair_eval/。
4. 每个命令都使用 uv run python -m benchmarks.rair_rag.run_routing_eval。
5. 脚本开头 set -euo pipefail。
```

---

## 10. 论文中如何突出两个主创新的价值

### 10.1 否定冲突的价值

失败模式：

```text
用户说“腿疼但是没流血”。
系统如果只看到“流血”，会误触发严重出血协议。
```

解决目标：

```text
降低协议误触发率 PFTR。
```

论文表述：

```text
Negation conflict is treated as a safety-critical routing failure. A risk term should not trigger an emergency protocol when it is explicitly negated by the user. Therefore, the proposed module identifies negation triggers and their scope, suppresses negated risks, and prevents the corresponding protocol from being selected.
```

### 10.2 多意图输入的价值

失败模式：

```text
用户说“我喘不上气，手机快没电了”。
系统如果只选择词面最明显或置信度最高的意图，可能优先处理 low_battery，而漏掉 respiratory_distress。
```

解决目标：

```text
提高高风险召回率 HRR。
```

论文表述：

```text
Multi-intent input is modeled as a risk-priority routing problem rather than a generic multi-label classification task. The system extracts all candidate risks, ranks them by risk severity and confidence, selects the primary emergency route, and preserves secondary risks or operational constraints for downstream response generation.
```

---

## 11. 推荐 README 更新

建议新增一段到 README：

```text
## RAIR-RAG Scope Notice

The current paper revision focuses on risk-aware input routing for offline RAG-based disaster emergency response. The core problem is not vector retrieval optimization, but pre-retrieval risk context construction under semantic perturbations. In particular, this revision focuses on two safety-critical input phenomena: negation conflict and multi-intent input. Negation conflict may cause false protocol triggering, while multi-intent input may cause high-risk intent miss. Differential Evolution is only used as an offline calibration tool for routing parameters.
```

Codex 提示词：

```text
请更新 README.md，新增 “RAIR-RAG Scope Notice” 小节。
要求：
1. 不删除原有 HSC-RAG 说明。
2. 新增说明必须指出新论文方向聚焦 pre-retrieval risk context construction。
3. 明确 negation conflict 和 multi-intent input 是主研究对象。
4. 明确 DE 只是 routing parameter calibration，不是主要性能来源。
5. 不要修改快速启动命令。
```

---

## 12. 最终落地任务清单

### 第一阶段：资料与标注体系

```text
[ ] 下载 WHO BEC PDF
[ ] 下载 WHO BEC Quick Cards
[ ] 下载 WHO PFA PDF
[ ] 人工检索应急管理部/中国地震局/国家应急广播/红十字会中文材料
[ ] 创建 guideline_sources.yaml
[ ] 创建 risk_taxonomy.yaml
[ ] 创建 annotation_codebook.md
```

### 第二阶段：样本构造

```text
[ ] 创建 negation_templates.yaml
[ ] 创建 multi_intent_templates.yaml
[ ] 创建 control_templates.yaml
[ ] 编写 generate_candidates.py
[ ] 生成候选样本
[ ] 人工筛选候选样本
```

### 第三阶段：人工标注

```text
[ ] 导出 annotation CSV
[ ] 双人独立标注
[ ] 计算一致性
[ ] 人工仲裁
[ ] 生成 gold JSONL
[ ] 划分 dev/test
```

### 第四阶段：算法改造

```text
[ ] 新增 negation_resolver.py
[ ] 新增 multi_intent_router.py
[ ] 新增 routing_policy.py
[ ] 新增 risk_router.py
[ ] 新增 routing_schema.py
[ ] 新增 routing_metrics.py
[ ] 新增 run_routing_eval.py
```

### 第五阶段：DE 与实验

```text
[ ] 新增 routing_policy_manual.yaml
[ ] 新增 de_routing_optimize.py
[ ] 在 dev split 上跑 DE
[ ] 固定 routing_policy_de.yaml
[ ] 在 test split 上跑主实验
[ ] 跑 negation 子集实验
[ ] 跑 multi-intent 子集实验
[ ] 导出表格和案例
```

---

## 13. 最终论文口径

论文标题建议：

```text
Risk-Aware Input Robustness for Offline RAG-Based Disaster Emergency Response:
Negation Conflict Resolution and Multi-Intent Priority Routing
```

中文标题：

```text
面向离线灾害应急 RAG 的风险感知输入鲁棒化方法：否定冲突消解与多意图优先级路由
```

核心贡献：

```text
本文提出一种面向离线灾害应急 RAG 的风险感知输入鲁棒化与路由控制方法，将否定冲突和多意图输入建模为检索前风险语义误解问题，并通过否定风险修正和多意图优先级路由减少协议误触发与高风险漏检。
```

贡献拆分：

```text
1. 构建权威指南依据驱动的灾害受困输入风险路由基准集，覆盖否定冲突、多意图输入以及其他补充扰动。
2. 提出否定冲突消解与多意图优先级路由方法，将原始输入转化为修正风险上下文，用于后续协议门控和 RAG 检索。
3. 使用差分进化对风险路由参数进行离线校准，并在独立 test split 上评估其对 PFTR、HRR 和 RouteAcc 的影响。
```

最重要的边界声明：

```text
本文不声称提出新的底层向量检索算法，也不声称首次提出否定检测或多意图识别。本文的贡献在于将这两类语义扰动引入离线灾害应急 RAG 的检索前风险路由阶段，并证明其对安全路径选择具有实际影响。
```

