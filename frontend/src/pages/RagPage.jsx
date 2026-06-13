import { useState } from "react";
import { searchRag } from "../services/api";

export function RagPage() {
  const [query, setQuery] = useState("我有点呼吸困难，胸口发紧。");
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      const data = await searchRag(query, topK);
      setResult(data);
    } catch (err) {
      setError(err.message || "RAG 检索失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="workspace-panel">
      <header className="panel-header">
        <div>
          <p className="eyebrow">Rag Search</p>
          <h2>RAG 检索验证</h2>
          <p className="muted">
            用单条问题观察路由维度、标签和最终命中的知识片段。
          </p>
        </div>
      </header>

      <form className="lab-form" onSubmit={handleSubmit}>
        <label className="field">
          <span>查询内容</span>
          <textarea
            rows={3}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="输入一句高风险或低证据问题..."
          />
        </label>

        <label className="field compact">
          <span>Top K</span>
          <input
            type="number"
            min="1"
            max="10"
            value={topK}
            onChange={(event) => setTopK(Number(event.target.value) || 5)}
          />
        </label>

        <div className="toolbar-actions">
          <button type="submit" className="primary-button" disabled={loading}>
            {loading ? "检索中..." : "执行检索"}
          </button>
        </div>
      </form>

      {error ? <p className="error">{error}</p> : null}

      {result ? (
        <div className="result-stack">
          <section className="result-card">
            <h3>路由结果</h3>
            <dl className="meta-grid">
              <div>
                <dt>维度</dt>
                <dd>{result.routing?.dimension || "未限定"}</dd>
              </div>
              <div>
                <dt>跨维度</dt>
                <dd>{result.routing?.cross_dimension ? "是" : "否"}</dd>
              </div>
              <div>
                <dt>标签</dt>
                <dd>{(result.routing?.tags || []).join(", ") || "无"}</dd>
              </div>
            </dl>
          </section>

          <section className="result-card">
            <h3>命中片段</h3>
            {result.results?.length ? (
              <div className="result-list">
                {result.results.map((item) => (
                  <article key={item.chunk_id} className="result-item">
                    <div className="result-topline">
                      <strong>{item.display_id || item.chunk_id}</strong>
                      <span>{item.dimension}</span>
                    </div>
                    <p>{item.text}</p>
                    <div className="result-metrics">
                      <span>distance {item.distance?.toFixed?.(3) ?? item.distance}</span>
                      <span>
                        final {item.final_distance?.toFixed?.(3) ?? item.final_distance}
                      </span>
                      <span>{item.risk}</span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p className="muted">当前没有命中结果。</p>
            )}
          </section>
        </div>
      ) : null}
    </section>
  );
}
