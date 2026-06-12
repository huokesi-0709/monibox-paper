# 配置体系重构基线与变更记录

> 记录时间：2026-06-12
> 背景：配置参数散落在 `.env`、扁平 `profiles/*.yaml`、`runtime/runtime_config.py` 及代码各处，维护困难。本次重构目标是将所有非机密结构化配置收拢到 YAML 分层体系，`.env` 仅保留 API Key 等机密。

---

## 重构前状态（Before）

### 1. 配置来源（4 处并存）

| 来源 | 文件/位置 | 覆盖范围 |
|---|---|---|
| **`.env`** | 项目根目录 | DeepSeek API Key、模型路径、RAG 参数、VAD 参数、TTS 参数、调试开关……几乎所有参数 |
| **`profiles/*.yaml`** | `profiles/` 下 7 个文件 | 平台差异覆盖，但**扁平键值对**，且各文件间大量重复 |
| **`runtime/runtime_config.py`** | 运行时配置中心 | `RuntimeConfig` dataclass + 手工 YAML 解析 + 环境变量映射表 `_ENV_FIELD_MAP` |
| **代码中散落 `os.getenv`** | `core/engine.py`、`language/backends.py`、`speech/*.py`、`devtools/*.py` 等 | 约 15 处直接读取环境变量 |

### 2. 现有 `profiles/*.yaml` 文件（扁平结构）

所有文件均包含大量重复默认值：

```yaml
# 所有 7 个文件都重复写这些：
tts_backend: sherpa
tts_model_dir: models/tts/sherpa/vits-icefall-zh-aishell3
tts_model_type: melo
tts_sherpa_sid: 173
tts_sherpa_noise_scale: 0.72
tts_sherpa_noise_scale_w: 0.85
llm_gpu_layers: 0
low_evidence_mode: true
# ...
```

### 3. 关键代码位置（重构前）

- **运行时配置中心**：`runtime/runtime_config.py`
  - `RuntimeConfig` dataclass（约 40 个字段）
  - `_ENV_FIELD_MAP`：环境变量 → 字段名映射（约 40 项）
  - `_load_profile_values()`：手工逐行解析 YAML（无层级、无类型安全）
  - 优先级：环境变量 > profiles/*.yaml > 代码默认值

- **构建侧配置**：`app/config.py`
  - `Settings` dataclass：DeepSeek API、Embedding、Chunking、RAG DB 路径
  - 直接读取 `.env`

- **散落读取点**（约 15 处）：
  - `core/engine.py`：VAD 参数、ASR arm delay、录音设备
  - `language/backends.py`：LLM backend、GGUF 路径、DeepSeek API
  - `speech/sapi.py`：TTS 轮询间隔、最大播放时长
  - `devtools/chat.py`、`devtools/win_e2e_demo.py`：多处重复读取

### 4. 核心问题

1. **重复严重**：7 个 profile 文件大量复制粘贴同一套默认值
2. **扁平无层级**：`tts_sherpa_noise_scale` 这种命名随着参数膨胀会越来越长
3. **类型不安全**：手工 `_parse_scalar` + `_coerce_like`，字符串/数字/布尔容易误解析
4. **维护负担重**：新增一个参数要改 `.env.example` + `_ENV_FIELD_MAP` + 可能多个 profile + 散落代码
5. **机密与非机密混放**：`.env` 里 API Key 和 `VAD_END_SIL_MS` 放在一起

---

## 重构后状态（After）

### 1. 配置来源（3 层 + 1 机密）

| 来源 | 文件/位置 | 覆盖范围 |
|---|---|---|
| **`profiles/base.yaml`** | 新增 | **全平台通用默认值**，分层结构化 |
| **`profiles/{platform}.yaml`** | 重写 | **只写与 base 的差异**，扁平 → 层级 |
| **`app/settings.py`** | 新增 | 统一加载器：递归 merge + Pydantic 类型校验 + `.env` 机密注入 |
| **`.env`** | 瘦身 | **仅保留机密**：`DEEPSEEK_API_KEY`、`HF_TOKEN` 等 |

### 2. 加载优先级

```
profiles/base.yaml（默认值）
    ↓ merge
profiles/{platform}.yaml（差异覆盖）
    ↓ Pydantic 校验
MoniboxConfig 对象
    ↓ .env 注入
最终配置（含 API Key 等机密）
```

### 3. 向后兼容策略

- `runtime/runtime_config.py` 保留，但内部改为调用 `app/settings.py` 的新加载器
- 原有 `load_runtime_config(profile)` 函数签名不变，调用方无需立即修改
- `.env` 中的非机密变量仍可读（作为兜底），但不再推荐新增

### 4. 待后续迁移（本批次不改）

以下文件中的 `os.getenv` 暂未迁移，留待后续迭代：

- `devtools/chat.py`（调试工具，非核心链路）
- `devtools/win_e2e_demo.py`（早期验证脚本）
- `core/engine.py` 中的录音设备/VAD 参数（运行时动态感测，需单独评估）
- `speech/sapi.py` 中的轮询间隔（设备相关微调）

---

## 变更文件清单

### 新增
- `profiles/base.yaml`
- `app/settings.py`
- `docs/CONFIG_REFACTOR_BASELINE.md`（本文件）

### 重写
- `profiles/windows.yaml`
- `profiles/radxa.yaml`
- `profiles/radxa_extreme.yaml`
- `profiles/radxa_full.yaml`
- `profiles/radxa_light.yaml`
- `profiles/text_mvp.yaml`
- `profiles/voice_mvp.yaml`

### 修改
- `runtime/runtime_config.py`（改为 facade，内部调用新加载器）
- `.env.example`（瘦身到只保留机密）

### 暂不改动（后续迭代）
- `app/config.py`（构建侧 Settings，逐步迁移到 settings.py）
- `core/engine.py`（运行时设备参数）
- `language/backends.py`（LLM backend 选择逻辑）
- `devtools/*.py`
- `speech/*.py`
