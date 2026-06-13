import { useEffect, useState } from "react";
import { getProtocolCatalog } from "../services/api";

export function ProtocolPage() {
  const [protocols, setProtocols] = useState([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getProtocolCatalog()
      .then((data) => setProtocols(data.items || []))
      .catch((err) => setError(err.message || "协议目录加载失败"));
  }, []);

  const filtered = protocols.filter((item) => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) {
      return true;
    }
    return `${item.protocol_id} ${item.name}`.toLowerCase().includes(keyword);
  });

  return (
    <section className="workspace-panel">
      <header className="panel-header">
        <div>
          <p className="eyebrow">Protocol</p>
          <h2>协议目录速查</h2>
          <p className="muted">
            这里适合检查高优先级协议是否已经入库，以及触发条件是否符合预期。
          </p>
        </div>
      </header>

      <label className="field">
        <span>过滤协议</span>
        <input
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="按协议名或 protocol_id 过滤..."
        />
      </label>

      {error ? <p className="error">{error}</p> : null}

      <div className="result-list">
        {filtered.slice(0, 24).map((item) => (
          <article key={item.protocol_id} className="result-item protocol-item">
            <div className="result-topline">
              <strong>{item.name}</strong>
              <span>priority {item.priority}</span>
            </div>
            <p>{item.protocol_id}</p>
            <div className="result-metrics">
              <span>actions {item.action_count}</span>
              <span>followups {item.followup_count}</span>
              <span>
                triggers {Object.keys(item.trigger || {}).length}
              </span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
