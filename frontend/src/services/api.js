const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      if (typeof data?.detail === "string" && data.detail) {
        message = data.detail;
      }
    } catch {
      // Ignore non-JSON error bodies and keep the HTTP status message.
    }
    throw new Error(message);
  }

  return response.json();
}

export function getHealth() {
  return request("/api/status/health");
}

export function postChatReply(message, sessionId) {
  return request("/api/chat/reply", {
    method: "POST",
    body: JSON.stringify({
      message,
      session_id: sessionId,
    }),
  });
}

export function searchRag(query, topK) {
  const params = new URLSearchParams({
    query,
    top_k: String(topK),
  });
  return request(`/api/rag/search?${params.toString()}`);
}

export function getProtocolCatalog() {
  return request("/api/protocol/catalog");
}
