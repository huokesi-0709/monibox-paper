# Local LLM Models

The local generation experiment uses Qwen1.5-0.5B-Chat-Q4_K_M in GGUF format.

Default expected path:

```text
models/llm/qwen1_5-0_5b-chat-q4_k_m.gguf
```

The GGUF file is intentionally not committed to Git. Place it manually before
running local generation experiments, or obtain it through Git LFS, a GitHub
Release asset, or an external model download source.

Related environment variables:

```text
LOCAL_LLM_MODEL_PATH=models/llm/qwen1_5-0_5b-chat-q4_k_m.gguf
LOCAL_LLM_N_CTX=2048
LOCAL_LLM_N_THREADS=4
```
