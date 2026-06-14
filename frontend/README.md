# MoniBox 前端

基于 **React + Vite** 的控制台原型，主要面向开发联调和演示。

## 包管理器

⚠️ **本项目使用 pnpm 管理依赖**，不再使用 npm。

如果你还没安装 pnpm：

```bash
npm install -g pnpm
```

## 常用命令

```bash
# 安装依赖
pnpm install

# 启动开发服务器
pnpm run dev

# 构建生产版本
pnpm run build

# 预览生产构建
pnpm run preview
```

## 目录结构

| 目录/文件       | 说明                             |
| --------------- | -------------------------------- |
| `src/App.jsx`   | 控制台总壳层                     |
| `src/pages/`    | Chat / Rag / Protocol / System   |
| `src/hooks/`    | 前端状态钩子                     |
| `src/services/` | 调用 FastAPI 的请求封装          |
