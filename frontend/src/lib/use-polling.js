import { useCallback, useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";

const globalCache = new Map();

/** Reusable polling hook: fetches a single endpoint on an interval, exposes
 *  `data`, `error` and a stable `refresh` callback. */
export function usePolling(path, { intervalMs = 2000, enabled = true, deps = [] } = {}) {
  const [data, setData] = useState(() => globalCache.get(path) || null);
  const [error, setError] = useState(null);
  const [isValidating, setIsValidating] = useState(!globalCache.has(path));

  const isPollingRef = useRef(false);

  // If path changes dynamically, immediately switch to the new path's cached data
  const lastPathRef = useRef(path);
  if (lastPathRef.current !== path) {
    lastPathRef.current = path;
    const cached = globalCache.get(path);
    if (cached) {
      setData(cached);
      if (isValidating) setIsValidating(false);
    } else {
      setData(null);
      if (!isValidating) setIsValidating(true);
    }
  }

  const refresh = useCallback(async () => {
    if (isPollingRef.current) return;
    isPollingRef.current = true;
    try {
      const res = await api.get(path);
      if (lastPathRef.current === path) {
        globalCache.set(path, res.data);
        setData(res.data);
        setError(null);
      }
    } catch (e) {
      console.error(`poll ${path} failed:`, e);
      if (lastPathRef.current === path) {
        setError(e);
      }
    } finally {
      if (lastPathRef.current === path) {
        isPollingRef.current = false;
        setIsValidating(false);
      } else {
        isPollingRef.current = false; // still need to unlock
      }
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

  return { data, error, isValidating, refresh };
}
