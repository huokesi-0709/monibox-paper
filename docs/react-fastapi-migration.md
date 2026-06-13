# MoniBox React + FastAPI 迁移骨架

当前仓库已经增加了两层新结构：

- `api/`: FastAPI 接口层
- `frontend/`: React + Vite 前端层

建议迁移顺序：

1. 先用 `api/status.py` 跑通前后端联调。
2. 再把 `api/chat.py` 接到 `runtime.orchestrator.MoniSession`。
3. 然后接入 `api/rag.py` 和 `api/protocol.py`。
4. `webui/` 保留为内部调试台，等 React 前端稳定后再决定是否下线。

本阶段目标不是替换全部功能，而是先把分层边界建立起来。
