import { useEffect, useState } from "react";
import { getHealth } from "../services/api";

export function useSystemHealth(pollMs = 15000) {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let disposed = false;

    async function refresh() {
      try {
        const data = await getHealth();
        if (disposed) {
          return;
        }
        setHealth(data);
        setError("");
      } catch (err) {
        if (disposed) {
          return;
        }
        setError(err.message || "系统状态获取失败");
      } finally {
        if (!disposed) {
          setLoading(false);
        }
      }
    }

    refresh();
    const timer = window.setInterval(refresh, pollMs);

    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [pollMs]);

  return {
    health,
    loading,
    error,
  };
}
