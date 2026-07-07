import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import Panel from "@/components/Panel";

const SEV = { info: "dim", success: "buy", warning: "warn", danger: "sell" };

export default function Notifications() {
  const [items, setItems] = useState([]);
  const load = async () => {
    const { data } = await api.get("/notifications?limit=100");
    setItems(data.notifications);
  };
  useEffect(() => {
    load();
    const i = setInterval(load, 3000);
    return () => clearInterval(i);
  }, []);

  const markAll = async () => { await api.post("/notifications/read-all"); load(); };

  return (
    <div className="space-y-4" data-testid="notifications-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 28, letterSpacing: "-0.02em" }}>Notifications.</h1>
          <p className="dim text-sm mt-1">All in-app events from signals, orders and strategies.</p>
        </div>
        <button className="btn" onClick={markAll} data-testid="notif-mark-all-read">Mark all read</button>
      </div>
      <Panel title="Feed" kicker={`${items.length}`}>
        <div className="cell-divider">
          {items.length === 0 && <div className="p-8 dim text-xs text-center">No notifications.</div>}
          {items.map((n) => (
            <div key={n.id} className="px-4 py-3 flex items-start gap-4" data-testid={`notif-${n.id}`}>
              <div className={`mono text-[10px] uppercase tracking-widest ${SEV[n.severity] || "dim"}`}>{n.kind}</div>
              <div className="flex-1">
                <div className="text-sm" style={{ fontFamily: "IBM Plex Sans", fontWeight: 600 }}>{n.title}</div>
                <div className="dim text-xs mt-1">{n.message}</div>
              </div>
              <div className="dim text-[10px] mono">{fmtDateTime(n.created_at)}</div>
              {!n.read && <span className="dot dot-live" />}
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
