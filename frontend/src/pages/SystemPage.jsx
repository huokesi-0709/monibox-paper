function buildRuntimeSummary(health, runtimePack) {
  const ragState = health.rag_db_exists ? "ready" : "missing";
  const packState = health.runtime_pack_exists ? "ready" : "missing";
  return `Profile ${health.profile} · LLM ${health.llm_backend} · TTS ${health.tts_backend} · RAG ${ragState} · Pack ${packState}`;
}

export function SystemPage({ health, loading, error }) {
  const runtimePack = health?.runtime_pack_summary || {};
  const topSubCategories = (runtimePack.top_sub_categories || []).slice(0, 6);
  const topTags = (runtimePack.top_tags || []).slice(0, 8);

  return (
    <section className="workspace-panel">
      <header className="panel-header">
        <div>
          <p className="eyebrow">System</p>
          <h2>系统状态总览</h2>
          <p className="muted">
            {health ? buildRuntimeSummary(health, runtimePack) : "等待系统状态返回..."}
          </p>
        </div>
      </header>

      {loading ? <p className="muted">正在获取系统状态...</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {health ? (
        <div className="system-layout">
          <section className="result-card system-hero">
            <div className="system-hero-copy">
              <p className="eyebrow">Overview</p>
              <h3>当前测试环境</h3>
              <div className="hero-facts">
                <div className="hero-fact">
                  <span>项目根目录</span>
                  <strong>{health.project_root}</strong>
                </div>
                <div className="hero-fact">
                  <span>最近构建时间</span>
                  <strong>{runtimePack.generated_at || "未生成"}</strong>
                </div>
              </div>
            </div>

            <div className="status-badges">
              <span className={`badge ${health.rag_db_exists ? "ok" : "warn"}`}>
                RAG DB {health.rag_db_exists ? "ready" : "missing"}
              </span>
              <span className={`badge ${health.runtime_pack_exists ? "ok" : "warn"}`}>
                Runtime Pack {health.runtime_pack_exists ? "ready" : "missing"}
              </span>
              <span className="badge neutral">LLM {health.llm_backend}</span>
              <span className="badge neutral">TTS {health.tts_backend}</span>
            </div>
          </section>

          <section className="result-card">
            <h3>运行状态</h3>
            <dl className="kv-grid">
              <div>
                <dt>状态</dt>
                <dd>{health.status}</dd>
              </div>
              <div>
                <dt>模式</dt>
                <dd>{health.profile}</dd>
              </div>
              <div>
                <dt>LLM</dt>
                <dd>{health.llm_backend}</dd>
              </div>
              <div>
                <dt>TTS</dt>
                <dd>{health.tts_backend}</dd>
              </div>
            </dl>
          </section>

          <section className="result-card">
            <h3>构建产物</h3>
            <dl className="kv-grid">
              <div>
                <dt>RAG DB</dt>
                <dd>{health.rag_db_exists ? "已生成" : "缺失"}</dd>
              </div>
              <div>
                <dt>Runtime Pack</dt>
                <dd>{health.runtime_pack_exists ? "已生成" : "缺失"}</dd>
              </div>
              <div>
                <dt>Chunk 数</dt>
                <dd>{String(runtimePack.chunk_count ?? "-")}</dd>
              </div>
              <div>
                <dt>数据源</dt>
                <dd>{runtimePack.source || "-"}</dd>
              </div>
            </dl>
          </section>

          <section className="result-card">
            <h3>路径与挂载</h3>
            <div className="path-stack">
              <div className="path-item">
                <span>项目根目录</span>
                <code>{health.project_root}</code>
              </div>
              <div className="path-item">
                <span>RAG DB 路径</span>
                <code>{health.rag_db_path}</code>
              </div>
              <div className="path-item">
                <span>Runtime Pack 路径</span>
                <code>{health.runtime_pack_path}</code>
              </div>
            </div>
          </section>

          <section className="result-card">
            <h3>热门子类</h3>
            <div className="pill-grid">
              {topSubCategories.length ? (
                topSubCategories.map(([label, count]) => (
                  <span key={label} className="data-pill">
                    <strong>{label}</strong>
                    <small>{count}</small>
                  </span>
                ))
              ) : (
                <p className="muted">暂无子类统计。</p>
              )}
            </div>
          </section>

          <section className="result-card">
            <h3>热门标签</h3>
            <div className="pill-grid">
              {topTags.length ? (
                topTags.map(([label, count]) => (
                  <span key={label} className="data-pill data-pill-wide">
                    <strong>{label}</strong>
                    <small>{count}</small>
                  </span>
                ))
              ) : (
                <p className="muted">暂无标签统计。</p>
              )}
            </div>
          </section>

          <section className="result-card">
            <h3>构建元数据</h3>
            <dl className="kv-grid">
              <div>
                <dt>Schema</dt>
                <dd>{runtimePack.schema_version || "-"}</dd>
              </div>
              <div>
                <dt>生成时间</dt>
                <dd>{runtimePack.generated_at || "-"}</dd>
              </div>
              <div>
                <dt>Chunk 数</dt>
                <dd>{String(runtimePack.chunk_count ?? "-")}</dd>
              </div>
              <div>
                <dt>Profile</dt>
                <dd>{health.profile}</dd>
              </div>
            </dl>
          </section>
        </div>
      ) : null}
    </section>
  );
}
