import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

/** Reusable polling hook: fetches a single endpoint on an interval, exposes
 *  `data`, `error` and a stable `refresh` callback. */
export function usePolling(path, { intervalMs = 2000, enabled = true, deps = [] } = {}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const res = await api.get(path);
      setData(res.data);
      setError(null);
    } catch (e) {
      console.error(`poll ${path} failed:`, e);
      setError(e);
    }
  }, [path]);

  useEffect(() => {
    if (!enabled) return;
    refresh();
    if (!intervalMs) return;
    const id = setInterval(refresh, intervalMs);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, intervalMs, enabled, ...deps]);

  return { data, error, refresh };
}
