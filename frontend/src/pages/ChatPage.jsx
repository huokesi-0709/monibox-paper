import { useState } from "react";
import { TEST_SCENARIOS } from "../data/testScenarios";

function formatDecision(debug) {
  const trace = debug?.trace || {};
  return trace.protocol_name || trace.decision || "待命中";
}

function riskTone(debug) {
  const priority = Number(debug?.trace?.priority || 0);
  if (priority >= 95) {
    return "critical";
  }
  if (priority >= 80) {
    return "warning";
  }
  return "calm";
}

export function ChatPage({ chat, onLaunchScenario }) {
  const [draft, setDraft] = useState("");
  const headlineStats = [
    { label: "当前会话", value: chat.sessionId },
    { label: "消息总数", value: String(chat.messages.length) },
    {
      label: "最近命中",
      value: formatDecision(chat.lastTurn?.debug),
    },
  ];

  async function handleSubmit(event) {
    event.preventDefault();
    const current = draft;
    setDraft("");
    await chat.sendMessage(current);
  }

  async function handleScenario(prompt) {
    setDraft("");
    await onLaunchScenario(prompt);
  }

  return (
    <section className="workspace-panel chat-workspace">
      <header className="panel-header">
        <div>
          <p className="eyebrow">Conversation Lab</p>
          <h2>连续对话测试</h2>
          <p className="muted">
            这里适合验证高风险协议、低证据分流、以及回复 trace 是否符合预期。
          </p>
        </div>

        <div className="toolbar-actions">
          <button
            type="button"
            className="ghost-button"
            onClick={chat.beginNewSession}
          >
            新会话
          </button>
        </div>
      </header>

      <section className="stats-strip">
        {headlineStats.map((item) => (
          <article key={item.label} className="stat-block">
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </article>
        ))}
      </section>

      <section className="scenario-strip">
        {TEST_SCENARIOS.map((scenario) => (
          <button
            key={scenario.id}
            type="button"
            className="scenario-chip"
            onClick={() => handleScenario(scenario.prompt)}
          >
            <span>{scenario.title}</span>
            <small>{scenario.risk}</small>
          </button>
        ))}
      </section>

      <div className="messages">
        {chat.messages.map((message) => (
          <article
            key={message.id}
            className={`message ${message.role} ${riskTone(message.debug)}`}
          >
            <div className="message-meta">
              <span className="role">{message.role}</span>
              <span>{new Date(message.createdAt).toLocaleTimeString()}</span>
            </div>
            <p>{message.content}</p>
            {message.debug?.trace ? (
              <dl className="trace-inline">
                <div>
                  <dt>decision</dt>
                  <dd>{message.debug.trace.decision || "-"}</dd>
                </div>
                <div>
                  <dt>protocol</dt>
                  <dd>{message.debug.trace.protocol_id || "-"}</dd>
                </div>
                <div>
                  <dt>backend</dt>
                  <dd>{message.debug.backend || "-"}</dd>
                </div>
              </dl>
            ) : null}
          </article>
        ))}
      </div>

      <form className="composer" onSubmit={handleSubmit}>
        <label className="field">
          <span>输入当前测试问题</span>
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="例如：我有点呼吸困难，感觉胸口发紧。"
            rows={4}
          />
        </label>

        <div className="composer-footer">
          <p className="muted">
            当前适合用来验证协议命中、trace 展示，以及会话切换。
          </p>
          <button type="submit" className="primary-button" disabled={chat.loading}>
            {chat.loading ? "发送中..." : "发送消息"}
          </button>
        </div>
      </form>
    </section>
  );
}
