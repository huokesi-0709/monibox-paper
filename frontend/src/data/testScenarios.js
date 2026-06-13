export const VIEW_DEFS = [
  {
    id: "chat",
    label: "聊天测试",
    summary: "连续对话、协议命中、回复 trace",
  },
  {
    id: "rag",
    label: "RAG 检索",
    summary: "单条问题路由、命中片段、距离排序",
  },
  {
    id: "protocol",
    label: "协议目录",
    summary: "查看高优先级协议与触发条件",
  },
  {
    id: "system",
    label: "系统状态",
    summary: "构建产物、后端模式、当前运行状态",
  },
];

export const TEST_SCENARIOS = [
  {
    id: "respiratory",
    title: "呼吸困难",
    risk: "高风险",
    prompt: "我有点呼吸困难，胸口发紧，感觉气不够。",
  },
  {
    id: "bleeding",
    title: "出血处理",
    risk: "高风险",
    prompt: "我腿上有伤口，一直在流血，现在该怎么办？",
  },
  {
    id: "trapped",
    title: "被压住无法移动",
    risk: "高风险",
    prompt: "我腿被压住了，动不了，也不知道要不要硬拉出来。",
  },
  {
    id: "panic",
    title: "恐慌发作",
    risk: "中风险",
    prompt: "我现在特别慌，心跳很快，感觉要撑不住了。",
  },
  {
    id: "thirst",
    title: "缺水与口干",
    risk: "低风险",
    prompt: "我很渴，嘴里很干，现在应该怎么节省体力和水？",
  },
  {
    id: "aftershock",
    title: "余震再次发生",
    risk: "高风险",
    prompt: "又开始震了，周围还在掉东西，我现在该怎么做？",
  },
];
