export function StatusPanel({ health, loading, error }) {
  return (
    <section className="status-panel">
      <div className="status-header">
        <p className="eyebrow">Health</p>
        <h2>API 状态</h2>
      </div>

      {loading ? <p className="muted">正在连接后端...</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {health ? (
        <dl className="kv-grid">
          <div>
            <dt>状态</dt>
            <dd>{health.status}</dd>
          </div>
          <div>
            <dt>LLM</dt>
            <dd>{String(health.llm_backend ?? "unknown")}</dd>
          </div>
          <div>
            <dt>TTS</dt>
            <dd>{String(health.tts_backend ?? "unknown")}</dd>
          </div>
          <div>
            <dt>知识库</dt>
            <dd>{health.rag_db_exists ? "ready" : "missing"}</dd>
          </div>
        </dl>
      ) : null}
    </section>
  );
}
