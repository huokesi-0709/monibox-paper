# MoniBox

MoniBox 是一个面向灾害受困场景的离线运行系统。当前仓库重点不是“功能尽量多”，而是先稳定一条可验证主链：

`文本输入 -> 协议/路由 -> RAG/低证据分流 -> 安全护栏 -> 输出`

## 项目定位与产品目标

MoniBox 面向的不是普通聊天机器人场景，而是灾害受困、断网、低算力、高风险的边缘交互场景。项目希望构建一套能够部署在端侧设备上的离线智能运行系统，使设备在缺乏网络和人工支持的情况下，仍能向受困者提供安抚、指引、问询和协议化应急响应。

核心目标不是“尽量聪明”，而是“在高风险条件下尽量可靠”。因此从设计上强调：

- **离线可运行**：不依赖稳定网络。
- **协议优先**：涉及安全和应急场景时优先走确定性规则，而不是把决策完全交给生成模型。
- **RAG 增强**：尽量让回答建立在本地知识库和结构化内容之上。
- **语音友好**：面向真实终端交互，输出必须适合播报。
- **面向边缘设备**：设计时考虑 Radxa 这类低功耗板卡的资源限制。
- **预留硬件融合能力**：未来不只做语音问答，还要和麦克风、扬声器、传感器、灯光和屏幕协同工作。

## 核心运行链路

```text
输入（文本/语音） → Engine → Orchestrator → 协议匹配 → RAG检索 → 低证据分流/LLM生成 → 安全护栏 → 响应管线 → TTS/播报
```

## 环境管理（uv）

本项目使用 uv 作为 Python 包与环境管理工具。

### 初始化环境

```bash
# 同步核心依赖（文本模式可直接运行）
uv sync

# 同步含 DeepSeek / OpenAI API 后端
uv sync --extra remote-llm

# 同步知识库构建依赖（Embedding / DeepSeek 构建客户端）
uv sync --extra knowledge

# 同步含语音链路的完整依赖
uv sync --extra voice

# 同步含本地 LLM（llama-cpp-python，macOS 上可能需要额外编译工具链）
uv sync --extra local-llm

# 含开发依赖
uv sync --extra dev
```

### 运行项目

```bash
# 文本模式
uv run monibox --mode text

# 语音模式（单轮验收）
uv run monibox --mode mic_vad --once
```

### 常用命令

```bash
uv run --extra dev pytest        # 运行测试
uv run monibox-chat --no_llm     # 纯文本 RAG 调试入口
uv run monibox-rag --q "我好冷"   # 快速查看 RAG 检索结果
uv pip list                      # 查看已安装包
uv lock                          # 更新 uv.lock
```

## 工程结构

### 应用入口 `app/`

`monibox` 命令是唯一正式运行入口，负责启动 `MainEngine`，并提供文本模式与 VAD 语音模式。

```bash
uv run monibox --mode text
uv run monibox --mode mic_vad --once
```

### 调试工具 `devtools/`

| 文件               | 职责                           |
| ------------------ | ------------------------------ |
| `chat.py`          | 纯文本 RAG / RAG+LLM 调试入口  |
| `rag_query.py`     | 单条查询的 RAG 检索结果查看器  |
| `protocol_mock.py` | 协议优先链路的轻量 smoke check |
| `win_e2e_demo.py`  | Windows 端到端语音验证（早期） |

### 运行协调层 `core/`

| 文件           | 职责                                                                                                        |
| -------------- | ----------------------------------------------------------------------------------------------------------- |
| `engine.py`    | **Engine**：启动全局资源、创建 Orchestrator、调度 ASR/播放/协调线程、管理“监听-识别-播报-暂停-恢复”生命周期 |
| `shared.py`    | 共享基础设施：引擎事件类型、全局队列、结构化追踪日志                                                        |
| `resources.py` | 全局资源预加载与管理（ASR/TTS/LLM/RAG 延迟加载）                                                            |

### 会话与策略层 `runtime/`（业务核心）

| 文件                   | 职责                                                                                 |
| ---------------------- | ------------------------------------------------------------------------------------ |
| `orchestrator.py`      | **Orchestrator**：主编排器，协调 handle() 主流程；组装 RAG、协议、安全、TTS 等子模块 |
| `protocol_matcher.py`  | 协议匹配引擎：做协议判定与状态处理                                                   |
| `protocol_fsm.py`      | 协议 QA 状态机，处理协议命中后的动作与回复                                           |
| `slot_parser.py`       | Slot 解析器：从用户输入抽取地点、yes/no 等 slot                                      |
| `rag_engine.py`        | RAG 检索引擎，基于 SQLite + sqlite-vec 做向量检索                                    |
| `generator.py`         | RAG 生成器：将检索结果交给 LLM 组织生成回复                                          |
| `evidence_router.py`   | 低证据路由：检索证据不足时走保守输出，而非强行生成                                   |
| `guard.py`             | 安全护栏：对输出内容进行安全过滤与处理                                               |
| `rewriter.py`          | 回复改写器：适配语音播报场景                                                         |
| `response_pipeline.py` | 响应管线：整合改写、重复抑制、TTS 调度                                               |
| `preprocessor.py`      | 文本预处理器：去重、句式转换、关键词风控等                                           |
| `primitives.py`        | 运行时原语：工作记忆、重复抑制、变体库、硬件接口抽象                                 |
| `emotions.py`          | 情绪策略与策略书                                                                     |
| `runtime_config.py`    | 运行时统一配置，收敛所有环境变量读取                                                 |
| `monitor.py`           | 性能与内存监控                                                                       |
| `topic_router.py`      | 主题路由器：基于 taxonomy 做标签路由                                                 |
| `scoring.py`           | 检索结果评分/重排序策略                                                              |

### 模型能力层

#### 语言模型 `language/`

| 文件            | 职责                          |
| --------------- | ----------------------------- |
| `backends.py`   | LLM 后端抽象与工厂            |
| `local.py`      | 基于 llama.cpp 的本地聊天实现 |

#### 语音链路 `speech/`

| 文件          | 职责                            |
| ------------- | ------------------------------- |
| `whisper.py`  | Faster-Whisper 语音识别实现     |
| `worker.py`   | ASR 工作线程封装                |
| `recorder.py` | 基础录音                        |
| `vad.py`      | VAD（语音活动检测）录音         |
| `pyttsx3.py`  | pyttsx3 离线 TTS                |
| `sapi.py`     | Windows SAPI TTS                |
| `sherpa.py`   | Sherpa 系列 TTS（端侧主推方案） |

### 设备抽象层 `devices/`

| 目录/文件   | 职责       |
| ----------- | ---------- |
| `player.py` | 音频播放器 |

### 数据与构建层

| 目录             | 职责                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------- |
| `knowledge/`     | 本地知识库资产：协议、策略、标签别名、情感策略、审核策略、chunk 元数据等              |
| `build/`         | 本地构建产物：`rag.db`、`runtime_pack.json`、日志与评测结果；默认不提交 Git          |
| `models/`        | 本地模型资产；当前保留必要的轻量模型元数据和音色样例                                  |
| `sql/schema.sql` | SQLite 数据库表结构定义                                                               |

### 配置层 `profiles/`

| 文件                          | 职责                                                      |
| ----------------------------- | --------------------------------------------------------- |
| `radxa.yaml` / `windows.yaml` | 平台级基线配置                                            |
| `*_mvp.yaml` / `radxa_*.yaml` | 运行配置文件（extreme、full、light、text_mvp、voice_mvp） |

### 测试层 `tests/`

`tests/` 保留给自动化测试；当前仓库没有已跟踪测试文件时，可先使用 `python -m compileall .` 做结构级导入检查。

### 知识库工具层 `knowledgekit/`

| 文件               | 职责                              |
| ------------------ | --------------------------------- |
| `client.py`        | DeepSeek API 客户端（构建期生成） |
| `embedder.py`      | Embedding 计算                    |
| `splitter.py`      | 文本切分（TTS 适配）              |
| `taxonomy.py`      | 知识分类体系                      |
| `schema.py`        | Chunk schema 定义与校验           |
| `fingerprint.py`   | 文本指纹去重                      |
| `parser.py`        | LLM JSON 输出解析                 |
| `store.py`         | sqlite-vec 向量数据库封装         |
| `tags.py`          | 标签注册与归一化                  |

## 核心调用链（以语音模式为例）

```text
monibox --mode mic_vad
  └─ Engine.start()
       ├─ 启动 ASR 线程 (speech.whisper / speech.worker)
       ├─ 启动音频播放线程
       ├─ 创建 Orchestrator
       └─ 协调线程调度事件队列
            └─ Orchestrator.handle(user_input)
                 ├─ ProtocolMatcher 协议匹配
                 │    ├─ 命中 → ProtocolFsm 执行协议动作/回复
                 │    └─ 未命中 → RagEngine 向量检索
                 ├─ EvidenceRouter 低证据分流
                 ├─ Generator / LLM 组织回复
                 ├─ Rewriter 改写
                 ├─ RepeatGuard + Guard 重复抑制与安全过滤
                 └─ ResponsePipeline → TTS → 音频播放
```

## 关键设计特点

1. **协议优先**：高风险应急场景优先命中确定性协议，不依赖模型自由发挥。
2. **离线运行**：ASR、Embedding、LLM、TTS 全部本地部署，不依赖网络。
3. **RAG 增强**：回答建立在本地 `rag.db` 知识库检索之上。
4. **低证据分流**：检索证据不足时走保守策略，避免生成幻觉内容。
5. **硬件预留**：`primitives.py` 中的 `HardwareIface` 已抽象 TTS/LED/屏幕接口，未来可直接对接 Radxa 真实外设。
