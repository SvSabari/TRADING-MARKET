/* eslint-disable */
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";

/** Encapsulates broker-state CRUD logic (schemas, connections, save, remove). */
export function useBrokerManagement() {
  const [conns, setConns] = useState([]);
  const [schemas, setSchemas] = useState({});
  const [available, setAvailable] = useState([]);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/brokers");
      setConns(data.connections); setAvailable(data.available);
      setSchemas(data.schemas);
    } catch (e) { console.error("brokers load failed:", e); }
  }, []);

  useEffect(() => {
    load();
    const q = new URLSearchParams(window.location.search);
    if (q.get("kite") === "connected") {
      toast.success("Zerodha Kite session connected for today.");
      window.history.replaceState({}, "", "/brokers");
    }
    if (q.get("upstox") === "connected") {
      toast.success("Upstox session connected for today.");
      window.history.replaceState({}, "", "/brokers");
    }
  }, [load]);

  const save = useCallback(async (selected, values, mockMode, schemaName, isDataFeed, isOrderExec) => {
    const payload = {
      broker: selected, mock_mode: mockMode,
      is_data_feed: isDataFeed,
      is_order_exec: isOrderExec,
      credentials: values,
      api_key: values.api_key || "",
      api_secret: values.api_secret || "",
    };
    await api.post("/brokers", payload);
    toast.success(`${schemaName || selected} saved (mock mode = ${mockMode})`);
    load();
  }, [load]);

  const setMode = useCallback(async (conn, isDataFeed, isOrderExec) => {
    const payload = {
      broker: conn.broker,
      mock_mode: conn.mock_mode,
      is_data_feed: isDataFeed,
      is_order_exec: isOrderExec,
    };
    try {
      await api.post("/brokers", payload);
      toast.success(`${conn.broker} mode updated`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to update broker mode");
    }
  }, [load]);

  const remove = useCallback(async (broker) => {
    await api.delete(`/brokers/${broker}`);
    toast.success("Disconnected");
    load();
  }, [load]);

  const connectKite = useCallback(async () => {
    try {
      const { data } = await api.get("/brokers/kite/login-url");
      toast.message("Redirecting to Zerodha…", { description: data.note });
      window.location.href = data.login_url;
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save API key + secret first, then turn off mock mode.");
    }
  }, []);

  const disconnectKite = useCallback(async () => {
    await api.post("/brokers/kite/disconnect");
    toast.success("Kite session cleared (mock mode re-enabled).");
    load();
  }, [load]);

  const connectAngel = useCallback(async () => {
    try {
      const { data } = await api.post("/brokers/angel/login");
      toast.success(`Angel session generated · ${data.session_date}`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Angel login failed — check creds + TOTP secret.");
    }
  }, [load]);

  const connectUpstox = useCallback(async () => {
    try {
      const { data } = await api.get("/brokers/upstox/login-url");
      toast.message("Redirecting to Upstox…", { description: data.note });
      window.location.href = data.login_url;
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save Upstox API key + secret first.");
    }
  }, []);

  const connectAliceblue = useCallback(async () => {
    try {
      const { data } = await api.get("/brokers/aliceblue/login-url");
      toast.message("Redirecting to Alice Blue…", { description: data.note });
      window.location.href = data.login_url;
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save Alice Blue API key (App Code) + Client ID first.");
    }
  }, []);

  return { conns, schemas, available, save, setMode, remove, connectKite, disconnectKite, connectAngel, connectUpstox, connectAliceblue, reload: load };
}
