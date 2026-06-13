import { TEST_SCENARIOS } from "../data/testScenarios";

function shortSessionId(sessionId) {
  if (!sessionId) {
    return "未分配";
  }
  if (sessionId.length <= 16) {
    return sessionId;
  }
  return `${sessionId.slice(0, 8)}...${sessionId.slice(-4)}`;
}

export function InspectorPanel({
  activeView,
  health,
  chat,
  onLaunchScenario,
}) {
  const runtimePack = health?.runtime_pack_summary || {};
  const latestTrace = chat.lastTurn?.debug?.trace || {};

  return (
    <aside className="inspector">
      <section className="inspector-section">
        <p className="eyebrow">Session</p>
        <h3>当前测试会话</h3>
        <dl className="kv-grid">
          <div>
            <dt>会话 ID</dt>
            <dd>{shortSessionId(chat.sessionId)}</dd>
          </div>
          <div>
            <dt>消息数</dt>
            <dd>{chat.messages.length}</dd>
          </div>
          <div>
            <dt>最近后端</dt>
            <dd>{chat.lastTurn?.debug?.backend || "pending"}</dd>
          </div>
          <div>
            <dt>当前工作区</dt>
            <dd>{activeView}</dd>
          </div>
        </dl>
      </section>

      <section className="inspector-section">
        <p className="eyebrow">Trace</p>
        <h3>最近一次命中</h3>
        {chat.lastTurn ? (
          <div className="trace-stack">
            <div className="trace-row">
              <span>决策</span>
              <strong>{latestTrace.decision || "未记录"}</strong>
            </div>
            <div className="trace-row">
              <span>协议 ID</span>
              <strong>{latestTrace.protocol_id || "-"}</strong>
            </div>
            <div className="trace-row">
              <span>协议名</span>
              <strong>{latestTrace.protocol_name || "-"}</strong>
            </div>
            <div className="trace-row">
              <span>优先级</span>
              <strong>{String(latestTrace.priority ?? "-")}</strong>
            </div>
          </div>
        ) : (
          <p className="muted">发送一条消息后，这里会显示本次命中的路由与协议。</p>
        )}
      </section>

      <section className="inspector-section">
        <p className="eyebrow">Scenarios</p>
        <h3>快速回归用例</h3>
        <div className="scenario-list">
          {TEST_SCENARIOS.slice(0, 4).map((scenario) => (
            <button
              key={scenario.id}
              type="button"
              className="scenario-item"
              onClick={() => onLaunchScenario(scenario.prompt)}
            >
              <span>{scenario.title}</span>
              <small>{scenario.risk}</small>
            </button>
          ))}
        </div>
      </section>

      <section className="inspector-section">
        <p className="eyebrow">Build</p>
        <h3>知识库构建摘要</h3>
        <dl className="kv-grid">
          <div>
            <dt>RAG DB</dt>
            <dd>{health?.rag_db_exists ? "ready" : "missing"}</dd>
          </div>
          <div>
            <dt>Runtime Pack</dt>
            <dd>{health?.runtime_pack_exists ? "ready" : "missing"}</dd>
          </div>
          <div>
            <dt>Chunk 数</dt>
            <dd>{String(runtimePack.chunk_count ?? "-")}</dd>
          </div>
          <div>
            <dt>生成时间</dt>
            <dd>{runtimePack.generated_at || "-"}</dd>
          </div>
        </dl>
      </section>
    </aside>
  );
}
