# 中文官方应急资料源抓取与可用信息提取包 v0.1

> 适用项目：MoniBox / RAIR-RAG  
> 任务目标：为“面向离线灾害应急 RAG 的风险感知输入鲁棒化方法：否定冲突消解与多意图优先级路由”准备中文权威资料源。  
> 当前日期：2026-06-29  
> 说明：本文件整理的是“中文官方/准官方应急科普资料源”的可用抓取结果、可信度分级、可直接转入数据集构建的标签依据，以及后续人工复核任务。它不是医学处置指南，也不能替代 WHO-ICRC Basic Emergency Care 或专业急救培训材料。

---

## 0. 这份文档解决什么问题

WHO-ICRC Basic Emergency Care 和 WHO Psychological First Aid 有稳定 PDF，可直接下载、引用和归档；但中国应急管理部、中国地震局、国家应急广播、中国红十字会这几个中文来源很多是栏目页、动态网页、微信文章、视频页或平台入口，不一定有统一 PDF 手册。

所以本文件采取以下策略：

1. **不把“入口页”误写成“条款依据”**：能直接抓到的只是入口页、栏目结构、部分安全短句，就只标为“入口依据”或“语言风格依据”。
2. **把中文来源分为四类用途**：官方来源入口、地震/自然灾害科普入口、面向公众的短句表达来源、红十字应急救护训练体系来源。
3. **把可直接使用的信息整理为数据集标签支持材料**：重点服务 RAIR-RAG 的两个核心任务，即否定冲突消解和多意图优先级路由。
4. **明确哪些内容还必须人工复核**：不能爬到原文的页面，需要人工访问、截图、保存网页 PDF 或下载材料后再进入最终数据集依据库。

---

## 1. 抓取结论总览

| 来源 | 抓取状态 | 是否可直接作为条款依据 | 推荐用途 | 备注 |
|---|---|---:|---|---|
| 应急管理部 `mem.gov.cn/kp/` | 已抓取栏目入口 | 不宜直接当条款 | 官方应急科普入口、自然灾害栏目入口、来源注册表 | 页面能证明这是应急管理部应急科普入口，但具体地震自救条款多在外链/微信 |
| 应急管理部自然灾害栏目 `mem.gov.cn/kp/zrzh/` | 已抓取列表页 | 不宜直接当条款 | 自然灾害栏目入口、后续人工检索入口 | 当前抓取页主要显示暴雨、强对流等近期科普 |
| 中国地震局 `cea.gov.cn` | 工具直接抓取失败，疑似 403 | 暂不可直接作为条款 | 需要人工浏览器访问或用地方地震局/地震灾害防御中心替代 | 不能把未抓取正文写进论文依据 |
| 国家应急广播 `cneb.gov.cn` | 已抓取首页部分内容 | 可作为公众语言风格/短句依据 | 地震避险短句、应急标识入口、公众表达风格 | 抓到“突遇地震勿慌张 护住头部找空场”等短句 |
| 中国红十字会 `redcross.org.cn` | 已抓取首页栏目结构 | 不宜直接当技术条款 | 证明中国红十字会有应急救援、应急救护、应急救护培训业务入口 | 具体止血/包扎/骨折材料需继续到训练中心或培训教材人工下载 |
| 中国红十字会总会训练中心 `crcntc.org.cn` | 已抓取服务平台入口 | 不宜直接当技术条款 | 证明“救在身边·红十字应急救护服务平台”、资源库、在线学习、AED 查询等入口 | 部分资源可能需要登录或动态加载 |

---

## 2. 已抓取来源与可用信息

### 2.1 应急管理部应急科普入口

**URL**

```text
https://www.mem.gov.cn/kp/
```

**抓取到的可用信息**

页面为“应急科普”入口，包含以下栏目：

```text
应急科普
生活安全
自然灾害
安全生产
应急科普场馆
国家应急管理科普库
```

页面底部显示主办单位为：

```text
应急管理部
```

**可用于论文/数据集的方式**

该页可以作为中文官方应急科普资料的入口来源，但不能直接作为“地震被困自救条款”的正文依据。

**推荐用途**

```yaml
source_id: mem_kp_portal
source_name: 中华人民共和国应急管理部-应急科普
source_url: https://www.mem.gov.cn/kp/
source_type: official_portal
authority_level: A
use_for:
  - official_source_registry
  - natural_disaster_source_entry
  - emergency_science_publicity_entry
not_use_for:
  - direct_first_aid_protocol_text
  - direct_self_rescue_rule_without_article_level_source
manual_followup:
  - 在该页面内进入“自然灾害”
  - 使用站内检索或浏览器搜索具体文章
  - 保存具体文章 URL、标题、发布日期、发布单位
```

---

### 2.2 应急管理部自然灾害栏目

**URL**

```text
https://www.mem.gov.cn/kp/zrzh/
```

**抓取到的可用信息**

页面为“首页 > 应急科普 > 自然灾害”栏目。当前列表主要是近期自然灾害科普和预警类内容，例如暴雨、强对流、山洪等。

**可用于论文/数据集的方式**

该页可作为自然灾害科普的栏目入口，但当前抓取结果没有直接得到“地震被埋压自救”“敲击求救”“保存体力”等条款正文。

**推荐用途**

```yaml
source_id: mem_natural_disaster_portal
source_name: 应急管理部-应急科普-自然灾害
source_url: https://www.mem.gov.cn/kp/zrzh/
source_type: official_topic_portal
authority_level: A
use_for:
  - natural_disaster_topic_entry
  - future_article_search
manual_followup_keywords:
  - 地震 被困 自救
  - 被埋压 保存体力 敲击 求救
  - 余震 坍塌 避险
  - 地震 受伤 自救
```

---

### 2.3 中国地震局资料

**URL**

```text
http://www.cea.gov.cn/
https://www.cea.gov.cn/
```

**抓取状态**

当前工具访问 `https://www.cea.gov.cn/` 时返回 403 Forbidden。  
因此，本次没有抓取到中国地震局官网正文内容。

**不能做什么**

不能在论文里写：

```text
中国地震局明确提出了某某条款……
```

除非后续人工浏览器打开具体页面并保存了证据。

**可以做什么**

将中国地震局作为后续人工复核入口：

```yaml
source_id: cea_manual_entry
source_name: 中国地震局
source_url: http://www.cea.gov.cn/
source_type: official_portal_manual_required
authority_level: A
crawl_status: blocked_or_unavailable_in_current_tool
manual_followup_required: true
use_for:
  - earthquake_disaster_prevention_authority_entry
  - manual_article_search
manual_followup_keywords:
  - 地震自救
  - 震后自救
  - 被埋压 自救
  - 防震减灾 科普
  - 地震避险 自救互救
```

**建议人工替代来源**

如果中国地震局主页难以直接检索，可优先人工查找以下直属/相关单位：

```text
中国地震灾害防御中心
中国地震应急搜救中心
中国地震台网中心
地方地震局官网
地方防震减灾科普馆
```

进入数据集之前，每一条材料都要记录：

```text
标题
发布单位
URL
发布日期
是否官网
是否转载
原始来源
截图/网页 PDF 存档路径
```

---

### 2.4 国家应急广播资料

**URL**

```text
https://www.cneb.gov.cn/
```

**抓取到的可用信息**

国家应急广播首页可抓到以下与本项目相关的公众应急表达：

```text
突遇地震勿慌张 护住头部找空场
遭遇地震老人莫慌 保护头部互相帮忙
应对灾害 提前准备应急包
紧急求救信号
应急避难 场所标识
```

页面还列出相关链接：

```text
应急管理部
中国地震局
中国应急信息网
联合国减少灾害风险办公室
```

**可用于论文/数据集的方式**

国家应急广播更适合作为“公众语言风格”和“短句化表达”的来源，而不是专业急救条款来源。

**推荐用途**

```yaml
source_id: cneb_homepage_safety_phrases
source_name: 国家应急广播-首页安全提示
source_url: https://www.cneb.gov.cn/
source_type: official_public_broadcast_portal
authority_level: A-
use_for:
  - public_facing_language_style
  - earthquake_shelter_short_instruction
  - emergency_symbol_entry
  - reference_reply_style
extracted_public_phrases:
  - 突遇地震勿慌张，护住头部找空场
  - 遭遇地震老人莫慌，保护头部互相帮忙
  - 应对灾害，提前准备应急包
related_entries:
  - 紧急求救信号
  - 应急避难场所标识
limitations:
  - 首页短句不能替代完整地震自救手册
  - 具体“紧急求救信号”等二级页面当前工具未成功抓取
manual_followup:
  - 人工打开“紧急求救信号”
  - 人工打开“应急避难场所标识”
  - 保存页面 PDF 或截图
```

---

### 2.5 中国红十字会资料

**URL**

```text
https://www.redcross.org.cn/
```

**抓取到的可用信息**

中国红十字会官网首页栏目包括：

```text
业务工作
  应急救援
  应急救护
我要参与
  应急救护培训
学习平台
  业务知识
  生命健康
  网上书屋
```

首页还列出：

```text
中国红十字会总会训练中心
总会备灾救灾中心
应急总医院
各省级红十字会
```

**可用于论文/数据集的方式**

中国红十字会官网可以支撑“公众急救和应急救护培训体系”这一来源层级，但首页不能直接支撑“出血按压、骨折固定”等具体操作条款。

**推荐用途**

```yaml
source_id: rcsc_homepage_first_aid_entry
source_name: 中国红十字会官网
source_url: https://www.redcross.org.cn/
source_type: official_red_cross_portal
authority_level: A
use_for:
  - emergency_rescue_and_first_aid_source_entry
  - first_aid_training_authority
  - red_cross_training_source_discovery
not_use_for:
  - direct_bleeding_protocol_text
  - direct_fracture_protocol_text
manual_followup:
  - 进入“应急救护”
  - 进入“应急救护培训”
  - 进入“网上书屋”
  - 检索“止血 包扎 固定 搬运”
  - 下载或截图具体培训材料
```

---

### 2.6 中国红十字会总会训练中心资料

**URL**

```text
https://www.crcntc.org.cn/
```

**抓取到的可用信息**

页面为：

```text
救在身边·红十字应急救护服务平台
```

可抓到的平台功能包括：

```text
培训报名
AED 查询
一体机查询
基地查询
资源库
  视频
  书籍
  课件
  图片
在线学习
红十字应急救护培训基地
红十字景区救护站
AED
应急救护一体机
```

**可用于论文/数据集的方式**

该平台可证明红十字总会训练中心有系统化的应急救护培训平台与资源库，但当前抓取结果没有公开显示具体“止血、包扎、骨折固定”等课件正文。部分资源可能需要登录或动态加载。

**推荐用途**

```yaml
source_id: rcsc_training_center_platform
source_name: 救在身边·红十字应急救护服务平台
source_url: https://www.crcntc.org.cn/
source_type: red_cross_training_platform
authority_level: A-
use_for:
  - first_aid_training_infrastructure
  - public_first_aid_resource_discovery
  - AED_and_training_base_context
not_use_for:
  - direct_medical_action_rule_without_material_download
manual_followup:
  - 人工登录或打开资源库
  - 下载公开书籍、课件、图片材料
  - 检索关键词：止血、包扎、骨折、固定、创伤、搬运、气道梗阻
  - 将下载材料登记到 source_registry
```

---

## 3. 可直接转入 RAIR-RAG 的中文资料卡片

注意：以下不是“完整急救处置协议”，而是从中文官方/准官方入口中可安全提取的资料用途卡片。医学具体动作仍建议优先依据 WHO-ICRC BEC；中文资料更多用于灾害场景、公众语言和本土化表达。

### Card CN-EQ-001：地震避险短句

```yaml
card_id: CN-EQ-001
source_id: cneb_homepage_safety_phrases
source_url: https://www.cneb.gov.cn/
source_type: official_public_broadcast_portal
risk_tags:
  - aftershock_or_collapse_hazard
  - earthquake_scene
  - environmental_hazard
usable_for:
  - reference_reply_style
  - short_public_instruction
  - earthquake_shelter_language
extracted_principle:
  - 突遇地震时应避免慌乱，保护头部，并尽量向空旷安全区域转移。
safe_reply_style:
  - 先护住头部，避开掉落物。等晃动减弱后，再向空旷处移动。
do_not_overclaim:
  - 不承诺绝对安全
  - 不要求用户在强烈晃动时盲目奔跑
dataset_use:
  - 可作为 aftershock_or_collapse_hazard 的 reference_reply 风格依据
  - 可用于多意图样本中的环境风险次要意图
```

### Card CN-EQ-002：老年人地震避险互助表达

```yaml
card_id: CN-EQ-002
source_id: cneb_homepage_safety_phrases
source_url: https://www.cneb.gov.cn/
risk_tags:
  - earthquake_scene
  - vulnerable_population
  - environmental_hazard
usable_for:
  - vulnerable_group_language
  - short_reply_style
extracted_principle:
  - 老年人在地震中应保持冷静、保护头部，并可进行互助。
safe_reply_style:
  - 先护住头部，别急着跑。身边有人能帮你一起移到安全处吗？
dataset_use:
  - 可作为 multi_intent 中“老人 + 地震 + 受伤/恐慌”的语言风格参考
limitations:
  - 不能直接扩展为复杂医疗处置
```

### Card CN-EQ-003：应急包/灾前准备

```yaml
card_id: CN-EQ-003
source_id: cneb_homepage_safety_phrases
source_url: https://www.cneb.gov.cn/
risk_tags:
  - preparedness
  - resource_constraint
usable_for:
  - low_battery_or_resource_context
  - emergency_kit_background
extracted_principle:
  - 灾害应对需要提前准备应急包。
safe_reply_style:
  - 现在先节省体力和电量。若身边有水、衣物、手电或哨子，放在伸手能拿到的位置。
dataset_use:
  - 可用于 low_battery / dehydration_or_resource_deprivation 的次要约束背景
limitations:
  - 不作为急救医学协议
```

### Card CN-ENTRY-001：应急管理部官方科普入口

```yaml
card_id: CN-ENTRY-001
source_id: mem_kp_portal
source_url: https://www.mem.gov.cn/kp/
risk_tags:
  - official_source_entry
  - natural_disaster
usable_for:
  - source_registry
  - authority_chain_description
extracted_principle:
  - 应急管理部官网设有应急科普入口，并包含自然灾害相关栏目。
dataset_use:
  - 数据集说明中可写“中文资料源首先从应急管理部应急科普入口和自然灾害栏目检索”
limitations:
  - 不能把入口页本身当作具体协议条款
```

### Card CN-ENTRY-002：中国红十字会应急救护入口

```yaml
card_id: CN-ENTRY-002
source_id: rcsc_homepage_first_aid_entry
source_url: https://www.redcross.org.cn/
risk_tags:
  - first_aid_training_entry
  - public_first_aid
usable_for:
  - source_registry
  - first_aid_training_authority_chain
extracted_principle:
  - 中国红十字会官网业务工作中包含应急救援和应急救护，并设有应急救护培训入口。
dataset_use:
  - 数据集说明中可写“公众急救相关材料优先从中国红十字会及其训练中心检索”
limitations:
  - 首页不能直接作为止血、包扎、骨折固定等操作的条款来源
```

### Card CN-ENTRY-003：红十字应急救护服务平台入口

```yaml
card_id: CN-ENTRY-003
source_id: rcsc_training_center_platform
source_url: https://www.crcntc.org.cn/
risk_tags:
  - first_aid_training_platform
  - AED
  - emergency_first_aid_resource
usable_for:
  - source_registry
  - first_aid_training_resource_discovery
extracted_principle:
  - 中国红十字会总会训练中心维护“救在身边·红十字应急救护服务平台”，包含培训报名、AED 查询、基地查询、资源库、在线学习等入口。
dataset_use:
  - 可作为后续人工下载应急救护课件、书籍、视频材料的入口
limitations:
  - 当前未抓取到具体公开课件正文
  - 部分资源可能需要登录或动态加载
```

---

## 4. 推荐建立的 source registry

建议在仓库中新增：

```text
benchmarks/sources/source_registry_china_official_v0.yaml
```

内容如下，可直接复制：

```yaml
version: china_official_sources_v0
created_at: "2026-06-29"
purpose: "RAIR-RAG authoritative Chinese source registry for disaster entrapment input routing"

sources:
  - source_id: mem_kp_portal
    name: 中华人民共和国应急管理部-应急科普
    url: https://www.mem.gov.cn/kp/
    organization: 中华人民共和国应急管理部
    source_type: official_portal
    authority_level: A
    crawl_status: fetched
    usable_for:
      - official_source_registry
      - natural_disaster_source_entry
      - emergency_science_publicity_entry
    limitations:
      - "入口页不能直接作为具体急救条款依据"
      - "具体地震自救条款需要进入文章级页面人工复核"

  - source_id: mem_natural_disaster_portal
    name: 应急管理部-应急科普-自然灾害
    url: https://www.mem.gov.cn/kp/zrzh/
    organization: 中华人民共和国应急管理部
    source_type: official_topic_portal
    authority_level: A
    crawl_status: fetched
    usable_for:
      - natural_disaster_topic_entry
      - future_article_search
    limitations:
      - "当前抓取页主要为自然灾害栏目列表"
      - "未直接抓取到地震被困自救条款正文"

  - source_id: cea_manual_entry
    name: 中国地震局
    url: http://www.cea.gov.cn/
    organization: 中国地震局
    source_type: official_portal_manual_required
    authority_level: A
    crawl_status: blocked_or_unavailable_in_current_tool
    usable_for:
      - earthquake_disaster_prevention_authority_entry
      - manual_article_search
    limitations:
      - "当前工具访问官网失败，不能直接引用未抓取正文"
    manual_followup_keywords:
      - 地震自救
      - 震后自救
      - 被埋压 自救
      - 防震减灾 科普
      - 地震避险 自救互救

  - source_id: cneb_homepage_safety_phrases
    name: 国家应急广播-首页安全提示
    url: https://www.cneb.gov.cn/
    organization: 中央广播电视总台国家应急广播
    source_type: official_public_broadcast_portal
    authority_level: A-
    crawl_status: fetched
    usable_for:
      - public_facing_language_style
      - earthquake_shelter_short_instruction
      - emergency_symbol_entry
      - reference_reply_style
    extracted_public_phrases:
      - 突遇地震勿慌张，护住头部找空场
      - 遭遇地震老人莫慌，保护头部互相帮忙
      - 应对灾害，提前准备应急包
    limitations:
      - "首页短句不能替代完整地震自救手册"
      - "二级页面需要人工复核"

  - source_id: rcsc_homepage_first_aid_entry
    name: 中国红十字会官网
    url: https://www.redcross.org.cn/
    organization: 中国红十字会
    source_type: official_red_cross_portal
    authority_level: A
    crawl_status: fetched
    usable_for:
      - emergency_rescue_and_first_aid_source_entry
      - first_aid_training_authority
      - red_cross_training_source_discovery
    limitations:
      - "首页不能直接作为止血、包扎、骨折固定等操作条款来源"

  - source_id: rcsc_training_center_platform
    name: 救在身边·红十字应急救护服务平台
    url: https://www.crcntc.org.cn/
    organization: 中国红十字会总会训练中心
    source_type: red_cross_training_platform
    authority_level: A-
    crawl_status: fetched
    usable_for:
      - first_aid_training_infrastructure
      - public_first_aid_resource_discovery
      - AED_and_training_base_context
    limitations:
      - "当前未抓取到具体公开课件正文"
      - "部分资源可能需要登录或动态加载"
```

---

## 5. 推荐建立的 extracted cards JSONL

建议在仓库中新增：

```text
benchmarks/sources/extracted_cards_china_official_v0.jsonl
```

内容如下，可直接复制：

```jsonl
{"card_id":"CN-EQ-001","source_id":"cneb_homepage_safety_phrases","risk_tags":["aftershock_or_collapse_hazard","earthquake_scene","environmental_hazard"],"usable_for":["reference_reply_style","short_public_instruction","earthquake_shelter_language"],"extracted_principle":"突遇地震时应避免慌乱，保护头部，并尽量向空旷安全区域转移。","safe_reply_style":"先护住头部，避开掉落物。等晃动减弱后，再向空旷处移动。","dataset_use":"用于 aftershock_or_collapse_hazard 的 reference_reply 风格依据；也可用于多意图样本中的环境风险次要意图。","limitations":["不承诺绝对安全","不要求用户在强烈晃动时盲目奔跑"]}
{"card_id":"CN-EQ-002","source_id":"cneb_homepage_safety_phrases","risk_tags":["earthquake_scene","vulnerable_population","environmental_hazard"],"usable_for":["vulnerable_group_language","short_reply_style"],"extracted_principle":"老年人在地震中应保持冷静、保护头部，并可进行互助。","safe_reply_style":"先护住头部，别急着跑。身边有人能帮你一起移到安全处吗？","dataset_use":"用于 multi_intent 中“老人 + 地震 + 受伤/恐慌”的语言风格参考。","limitations":["不能直接扩展为复杂医疗处置"]}
{"card_id":"CN-EQ-003","source_id":"cneb_homepage_safety_phrases","risk_tags":["preparedness","resource_constraint"],"usable_for":["low_battery_or_resource_context","emergency_kit_background"],"extracted_principle":"灾害应对需要提前准备应急包。","safe_reply_style":"现在先节省体力和电量。若身边有水、衣物、手电或哨子，放在伸手能拿到的位置。","dataset_use":"用于 low_battery / dehydration_or_resource_deprivation 的次要约束背景。","limitations":["不作为急救医学协议"]}
{"card_id":"CN-ENTRY-001","source_id":"mem_kp_portal","risk_tags":["official_source_entry","natural_disaster"],"usable_for":["source_registry","authority_chain_description"],"extracted_principle":"应急管理部官网设有应急科普入口，并包含自然灾害相关栏目。","dataset_use":"数据集说明中可写中文资料源首先从应急管理部应急科普入口和自然灾害栏目检索。","limitations":["不能把入口页本身当作具体协议条款"]}
{"card_id":"CN-ENTRY-002","source_id":"rcsc_homepage_first_aid_entry","risk_tags":["first_aid_training_entry","public_first_aid"],"usable_for":["source_registry","first_aid_training_authority_chain"],"extracted_principle":"中国红十字会官网业务工作中包含应急救援和应急救护，并设有应急救护培训入口。","dataset_use":"数据集说明中可写公众急救相关材料优先从中国红十字会及其训练中心检索。","limitations":["首页不能直接作为止血、包扎、骨折固定等操作的条款来源"]}
{"card_id":"CN-ENTRY-003","source_id":"rcsc_training_center_platform","risk_tags":["first_aid_training_platform","AED","emergency_first_aid_resource"],"usable_for":["source_registry","first_aid_training_resource_discovery"],"extracted_principle":"中国红十字会总会训练中心维护救在身边·红十字应急救护服务平台，包含培训报名、AED 查询、基地查询、资源库、在线学习等入口。","dataset_use":"作为后续人工下载应急救护课件、书籍、视频材料的入口。","limitations":["当前未抓取到具体公开课件正文","部分资源可能需要登录或动态加载"]}
```

---

## 6. 对 RAIR-RAG 数据集标签的影响

### 6.1 哪些风险标签能被中文来源支撑

| 风险标签 | 中文来源支撑强度 | 主要来源 | 使用方式 |
|---|---:|---|---|
| aftershock_or_collapse_hazard | 中 | 国家应急广播、应急管理部自然灾害栏目、中国地震局待人工复核 | 环境风险、地震避险短句 |
| trapped_or_entrapment | 弱到中 | 需要中国地震局/应急管理部具体文章补强 | 当前不能只靠已抓取材料支撑 |
| earthquake_scene | 中 | 国家应急广播、应急管理部自然灾害栏目 | 场景标签 |
| resource_constraint | 中 | 国家应急广播应急包短句；MoniBox 场景设计 | 次要约束，不能当医学主风险 |
| public_first_aid | 中 | 中国红十字会、中国红十字会训练中心入口 | 急救训练来源入口 |
| severe_bleeding | 中文入口支撑弱，医学条款应以 WHO-ICRC 为主 | 红十字入口 + WHO-ICRC BEC | 不能直接从红十字首页提取具体操作 |
| trauma_or_fracture | 中文入口支撑弱，医学条款应以 WHO-ICRC 为主 | 红十字入口 + WHO-ICRC BEC | 需要下载培训材料后再增强 |

### 6.2 对两个主创新的直接帮助

#### 否定冲突消解

中文资料的作用：

```text
帮助定义“什么风险不应误触发”。
```

例如：

```text
“腿疼但是没流血”
```

如果 severe_bleeding 的医学处理依据来自 WHO-ICRC，而中文资料只提供公众表达与场景补充，那么数据集标注时应写：

```yaml
risk_mentions:
  - pain
  - bleeding
negated_risks:
  - severe_bleeding
positive_risks:
  - trauma_or_fracture
should_not_trigger:
  - prot_bleeding_control
authority_chain:
  - WHO-ICRC BEC for bleeding as medical risk
  - Red Cross China as first-aid training authority entry
```

也就是说，中文红十字目前更多支撑“公众急救训练来源入口”，具体出血协议仍用 WHO-ICRC BEC 更稳。

#### 多意图优先级路由

中文资料的作用：

```text
帮助定义灾害场景中的环境风险和资源约束表达。
```

例如：

```text
“我喘不上气，手机快没电了，外面还在晃。”
```

可以标注为：

```yaml
primary_intent: respiratory_distress
secondary_intents:
  - low_battery
  - aftershock_or_collapse_hazard
route_reason:
  - respiratory_distress 是生命威胁型风险
  - low_battery 是运行/通信约束
  - aftershock_or_collapse_hazard 是环境风险
authority_chain:
  - WHO-ICRC BEC for breathing risk
  - CNEB earthquake shelter phrases for earthquake environmental hazard language
```

这能清楚体现：

```text
RAG 前风险上下文不是简单关键词集合，而是主风险 + 次要风险 + 系统约束。
```

---

## 7. 后续必须人工完成的下载/保存任务

### 7.1 应急管理部

进入：

```text
https://www.mem.gov.cn/kp/
https://www.mem.gov.cn/kp/zrzh/
```

人工检索并保存：

```text
地震 被困 自救
被埋压 保存体力 敲击 求救
余震 坍塌 避险
地震 受伤 自救
```

保存方式：

```text
1. 保存网页为 PDF
2. 截图标题、发布时间、发布单位
3. 复制文章 URL
4. 记录是否为应急管理部原创或转载
5. 若是微信文章，记录公众号主体和应急管理部是否在官网转载/链接
```

文件命名建议：

```text
benchmarks/sources/archive/mem_earthquake_self_rescue_001.pdf
benchmarks/sources/archive/mem_earthquake_self_rescue_001.png
benchmarks/sources/archive/mem_earthquake_self_rescue_001.yaml
```

### 7.2 中国地震局

人工打开：

```text
http://www.cea.gov.cn/
```

检索：

```text
防震减灾 科普
地震自救
地震避险
被埋压 自救
震后自救
```

如果主站不可用，查找：

```text
中国地震灾害防御中心
中国地震应急搜救中心
地方地震局官网
地方防震减灾科普馆
```

注意：

```text
只有官方机构网站、政府网站、学校/科普馆官方发布页可进入正式 source_registry。
普通自媒体文章不能进入核心依据。
```

### 7.3 国家应急广播

人工打开：

```text
https://www.cneb.gov.cn/
```

重点保存：

```text
突遇地震勿慌张 护住头部找空场
遭遇地震老人莫慌 保护头部互相帮忙
紧急求救信号
应急避难场所标识
```

当前二级页面抓取不稳定，建议用浏览器人工打开并保存网页 PDF。

### 7.4 中国红十字会

人工打开：

```text
https://www.redcross.org.cn/
https://www.crcntc.org.cn/
```

重点查找：

```text
应急救护
应急救护培训
网上书屋
资源库
止血
包扎
骨折
固定
搬运
创伤救护
气道梗阻
```

如果需要登录：

```text
不强行爬取
记录登录门槛
只使用公开可访问材料
```

---

## 8. 放入仓库的建议目录

```text
benchmarks/
  sources/
    source_registry_china_official_v0.yaml
    extracted_cards_china_official_v0.jsonl
    archive/
      mem/
      cea/
      cneb/
      redcross/
    notes/
      manual_followup_checklist.md

docs/
  paper/
    china_official_sources_extraction_report.md
```

---

## 9. Codex 提示词：创建 source registry

```text
你现在在 monibox-paper 仓库中工作。请新增目录 benchmarks/sources/，并创建 benchmarks/sources/source_registry_china_official_v0.yaml。

文件内容用于记录 RAIR-RAG 中文官方/准官方资料源。请包含以下来源：
1. 应急管理部应急科普：https://www.mem.gov.cn/kp/
2. 应急管理部自然灾害栏目：https://www.mem.gov.cn/kp/zrzh/
3. 中国地震局：http://www.cea.gov.cn/，标记为 manual_required，因为当前工具抓取失败
4. 国家应急广播：https://www.cneb.gov.cn/
5. 中国红十字会：https://www.redcross.org.cn/
6. 救在身边·红十字应急救护服务平台：https://www.crcntc.org.cn/

每个 source 至少包含：
source_id, name, url, organization, source_type, authority_level, crawl_status, usable_for, limitations, manual_followup_keywords。

注意：
- 不要把入口页写成具体急救条款依据；
- 中国地震局来源必须标记 crawl_status: blocked_or_unavailable_in_current_tool；
- 红十字来源只能作为应急救护训练入口，不能直接作为止血/骨折具体操作条款。
```

---

## 10. Codex 提示词：创建 extracted cards JSONL

```text
请在 monibox-paper 仓库中创建 benchmarks/sources/extracted_cards_china_official_v0.jsonl。

每行是一个 JSON object，字段包括：
card_id, source_id, risk_tags, usable_for, extracted_principle, safe_reply_style, dataset_use, limitations。

至少写入以下 6 张卡片：
CN-EQ-001: 国家应急广播地震避险短句
CN-EQ-002: 国家应急广播老人地震避险互助表达
CN-EQ-003: 国家应急广播应急包/资源约束表达
CN-ENTRY-001: 应急管理部应急科普入口
CN-ENTRY-002: 中国红十字会应急救护入口
CN-ENTRY-003: 救在身边红十字应急救护服务平台入口

注意：
- 卡片只写可安全归纳的原则，不要写具体医疗操作；
- severe_bleeding、trauma_or_fracture 的具体医学条款仍应引用 WHO-ICRC BEC；
- 中文来源更多用于灾害场景、公众语言和来源入口。
```

---

## 11. Codex 提示词：创建人工复核清单

```text
请创建 benchmarks/sources/notes/manual_followup_checklist.md。

内容包括四部分：
1. 应急管理部人工检索任务
2. 中国地震局人工检索任务
3. 国家应急广播人工保存任务
4. 中国红十字会/训练中心人工下载任务

每个任务包括：
- 入口 URL
- 检索关键词
- 需要保存的材料
- 文件命名规则
- 是否可作为核心条款依据的判断标准

特别强调：
- 网页入口不能直接作为具体协议条款；
- 微信/央视频/动态页面需要截图、URL、发布主体和转载关系；
- 只有具体文章、教材、课件、手册才能进入 evidence-level source。
```

---

## 12. 论文里应该怎么写这部分

推荐写法：

```text
中文资料源主要用于补充灾害场景、本土化表达和公众应急传播语境。本文首先检索应急管理部应急科普入口、自然灾害栏目、国家应急广播、中国红十字会及其应急救护服务平台，并建立 source registry 记录来源类型、发布主体、可用范围和限制。由于部分中文资料以栏目页、微信文章、视频或动态平台形式发布，本文不将入口页直接作为具体急救条款依据，而是仅在文章级或教材级资料可复核时将其纳入 evidence-level source。对于呼吸困难、严重出血、创伤、休克和失温等医学风险，主要依据 WHO-ICRC Basic Emergency Care；中文资料则用于灾害受困表达、地震环境风险、公众短句风格和本土化标签映射。
```

---

## 13. 最终建议

当前中文来源可以支持：

```text
1. 官方中文资料入口链；
2. 地震/自然灾害场景背景；
3. 面向公众的短句化表达；
4. 红十字应急救护训练体系来源；
5. 多意图中的环境风险和资源约束标签。
```

当前中文来源暂时不能单独支持：

```text
1. 严重出血完整处置协议；
2. 骨折固定完整协议；
3. 挤压伤医学处理协议；
4. 呼吸困难医学处理协议；
5. 具体被埋压自救条款。
```

这些仍需：

```text
WHO-ICRC BEC
WHO PFA
红十字公开教材/课件
中国地震局或应急管理部具体文章级材料
```

换句话说，中文材料目前最适合补充 RAIR-RAG 的“场景和语言”，医学安全边界仍要靠 WHO-ICRC 与红十字具体教材来兜底。
