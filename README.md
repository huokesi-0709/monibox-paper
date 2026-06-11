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
输入（文本/语音） → MainEngine → MoniSession → 协议匹配 → RAG检索 → 低证据分流/LLM生成 → 安全护栏 → 输出管线 → TTS/播报
```

## 环境管理（uv）

本项目使用 uv 作为 Python 包与环境管理工具。

### 初始化环境

```bash
# 同步核心依赖（文本模式可直接运行）
uv sync

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
uv run python -m apps.runtime_edge --mode text

# 语音模式（单轮验收）
uv run python -m apps.runtime_edge --mode mic_vad --once
```

### 常用命令

```bash
uv run pytest                    # 运行测试
uv run python -m apps.chat       # 纯文本调试入口
uv pip list                      # 查看已安装包
uv lock                          # 更新 uv.lock
```

> 注：旧版 `requirements.txt` 已迁移至 `pyproject.toml`，后续优先使用 uv 管理依赖。

## 工程结构

### 1. 入口层 `apps/`

| 文件               | 职责                                                                      |
| ------------------ | ------------------------------------------------------------------------- |
| `runtime_edge.py`  | **当前主入口**，支持 `--mode text` 纯文本模式和 `--mode mic_vad` 语音模式 |
| `chat.py`          | 纯文本 RAG / RAG+LLM 调试入口                                             |
| `win_e2e_demo.py`  | Windows 端到端语音验证（早期）                                            |
| `win_e2e_queue.py` | 队列式音频链路实验入口                                                    |

### 2. 运行协调层 `monibox/core_loop/`

| 文件                  | 职责                                                                                                           |
| --------------------- | -------------------------------------------------------------------------------------------------------------- |
| `main_engine.py`      | **MainEngine**：启动全局资源、创建 MoniSession、调度 ASR/播放/协调线程、管理“监听-识别-播报-暂停-恢复”生命周期 |
| `models.py`           | 引擎事件与事件类型定义                                                                                         |
| `queues.py`           | 全局输入/输出队列                                                                                              |
| `resource_manager.py` | 全局资源预加载与管理                                                                                           |
| `trace_logger.py`     | 运行时交互追踪与日志                                                                                           |

### 3. 会话与策略层 `monibox/runtime/`（业务核心）

| 文件                     | 职责                                                                                |
| ------------------------ | ----------------------------------------------------------------------------------- |
| `session.py`             | **MoniSession**：主编排器，协调 handle() 主流程；组装 RAG、协议、安全、TTS 等子模块 |
| `protocol_engine.py`     | 协议引擎：做协议判定与状态处理                                                      |
| `protocol_handler.py`    | 协议 QA 状态机，处理协议命中后的动作与回复                                          |
| `protocol_context.py`    | 协议上下文解析（地点、是否判断等 slot 抽取）                                        |
| `rag_engine.py`          | RAG 检索引擎，基于 SQLite + sqlite-vec 做向量检索                                   |
| `rag_generator.py`       | 将 RAG 检索结果交给 LLM 组织生成回复                                                |
| `low_evidence_router.py` | 低证据分流：检索证据不足时走保守输出，而非强行生成                                  |
| `safety_guard.py`        | 安全护栏：对输出内容进行安全过滤与处理                                              |
| `response_rewriter.py`   | 回复改写，适配语音播报场景                                                          |
| `output_pipeline.py`     | 输出管线：整合改写、重复抑制、TTS 调度                                              |
| `text_pipeline.py`       | 文本预处理（去重、句式转换、关键词风控等）                                          |
| `memory.py`              | 工作记忆（WorkingMemory），维护会话短期上下文                                       |
| `emotion_strategies.py`  | 情绪策略与策略书                                                                    |
| `repeat_guard.py`        | 重复抑制，避免连续相同播报                                                          |
| `variants.py`            | 回复变体生成，防止机械重复                                                          |
| `runtime_config.py`      | 运行时统一配置，收敛所有环境变量读取                                                |
| `perf_monitor.py`        | 性能监控                                                                            |
| `hardware_iface.py`      | 硬件接口抽象（TTS、LED、屏幕），当前以 MockHardware 为主                            |

### 4. 模型能力层

#### LLM `monibox/llm/`

| 文件                | 职责                          |
| ------------------- | ----------------------------- |
| `backend.py`        | LLM 后端抽象与工厂            |
| `llama_cpp_chat.py` | 基于 llama.cpp 的本地聊天实现 |

#### ASR `monibox/asr/`

| 文件                    | 职责                        |
| ----------------------- | --------------------------- |
| `faster_whisper_asr.py` | Faster-Whisper 语音识别实现 |
| `asr_worker.py`         | ASR 工作线程封装            |

#### TTS `monibox/tts/`

| 文件             | 职责                            |
| ---------------- | ------------------------------- |
| `pyttsx3_tts.py` | pyttsx3 离线 TTS                |
| `sapi_tts.py`    | Windows SAPI TTS                |
| `sherpa_tts.py`  | Sherpa 系列 TTS（端侧主推方案） |

### 5. 音频与硬件抽象层

| 目录/文件                       | 职责                    |
| ------------------------------- | ----------------------- |
| `monibox/audio/base_recorder.py`     | 基础录音                |
| `monibox/audio/vad.py` | VAD（语音活动检测）录音 |
| `monibox/hw/player.py`    | 音频播放器              |
| `monibox/hw/mock_hw.py`         | 硬件 mock（占位）       |

### 6. 数据与构建层

| 目录             | 职责                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------- |
| `knowledge/`     | 本地知识库资产：协议、策略、标签别名、情感策略、审核策略、chunk 元数据等              |
| `build/`         | 构建产物：`rag.db`（向量数据库）、`runtime_pack.json`（运行时配置包）、日志与评测结果 |
| `sql/schema.sql` | SQLite 数据库表结构定义                                                               |
| `scoring/`       | 评分/重排序策略                                                                       |

### 7. 配置层 `config/`

| 文件                          | 职责                                                      |
| ----------------------------- | --------------------------------------------------------- |
| `radxa.yaml` / `windows.yaml` | 平台级基线配置                                            |
| `profiles/`                   | 运行配置文件（extreme、full、light、text_mvp、voice_mvp） |

### 8. 测试层 `tests/`

| 文件                                                   | 职责                 |
| ------------------------------------------------------ | -------------------- |
| `test_session_integration.py`                          | 会话集成测试         |
| `test_protocol_trigger.py`                             | 协议触发测试         |
| `test_safety_guard.py`                                 | 安全护栏测试         |
| `test_runtime_config.py` / `test_runtime_trace.py`     | 运行时配置与追踪测试 |
| `test_stage_2_sources.py` ~ `test_stage_5_emotions.py` | 分阶段验收测试       |
| `test_tts_experience.py`                               | TTS 体验测试         |
| `test_asr_corrections.py`                              | ASR 纠错测试         |

## 核心调用链（以语音模式为例）

```text
apps/runtime_edge.py --mode mic_vad
  └─ MainEngine.start()
       ├─ 启动 ASR 线程 (faster_whisper_asr / asr_worker)
       ├─ 启动音频播放线程
       ├─ 创建 MoniSession
       └─ 协调线程调度事件队列
            └─ MoniSession.handle(user_input)
                 ├─ ProtocolEngine 协议匹配
                 │    ├─ 命中 → ProtocolHandler 执行协议动作/回复
                 │    └─ 未命中 → RagEngine 向量检索
                 ├─ LowEvidenceRouter 低证据分流
                 ├─ RagGenerator / LLM 组织回复
                 ├─ ResponseRewriter 改写
                 ├─ RepeatGuard + SafetyGuard 重复抑制与安全过滤
                 └─ OutputPipeline → TTS → 音频播放
```

## 关键设计特点

1. **协议优先**：高风险应急场景优先命中确定性协议，不依赖模型自由发挥。
2. **离线运行**：ASR、Embedding、LLM、TTS 全部本地部署，不依赖网络。
3. **RAG 增强**：回答建立在本地 `rag.db` 知识库检索之上。
4. **低证据分流**：检索证据不足时走保守策略，避免生成幻觉内容。
5. **硬件预留**：`hardware_iface.py` 已抽象 TTS/LED/屏幕接口，未来可直接对接 Radxa 真实外设。
