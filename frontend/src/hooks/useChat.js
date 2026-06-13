import { startTransition, useState } from "react";
import { postChatReply } from "../services/api";

function createSeedMessage() {
  return {
    id: "welcome",
    role: "assistant",
    content: "测试台已经连上真实后端。你可以直接发送高风险场景，观察协议命中和 trace。",
    createdAt: new Date().toISOString(),
    debug: null,
  };
}

function createSessionId() {
  return `session-${Date.now().toString(36)}`;
}

export function useChat() {
  const [sessionId, setSessionId] = useState(createSessionId);
  const [messages, setMessages] = useState([createSeedMessage()]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastTurn, setLastTurn] = useState(null);

  function beginNewSession() {
    startTransition(() => {
      setSessionId(createSessionId());
      setMessages([createSeedMessage()]);
      setError("");
      setLastTurn(null);
    });
  }

  async function sendMessage(text) {
    const trimmed = (text || "").trim();
    if (!trimmed || loading) {
      return null;
    }

    const userMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
      createdAt: new Date().toISOString(),
      debug: null,
    };

    setLoading(true);
    setError("");
    setMessages((current) => [...current, userMessage]);

    try {
      const data = await postChatReply(trimmed, sessionId);
      const assistantMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: data.reply || "暂无回复",
        createdAt: new Date().toISOString(),
        debug: data.debug || null,
      };

      startTransition(() => {
        setMessages((current) => [...current, assistantMessage]);
        setLastTurn({
          ...data,
          prompt: trimmed,
        });
      });

      return data;
    } catch (err) {
      const failureMessage = {
        id: `assistant-error-${Date.now()}`,
        role: "assistant",
        content: `请求失败：${err.message || "未知错误"}`,
        createdAt: new Date().toISOString(),
        debug: null,
      };

      startTransition(() => {
        setMessages((current) => [...current, failureMessage]);
        setError(err.message || "未知错误");
      });
      return null;
    } finally {
      setLoading(false);
    }
  }

  return {
    sessionId,
    messages,
    loading,
    error,
    lastTurn,
    beginNewSession,
    sendMessage,
  };
}
