import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtInt } from "@/lib/format";

export default function StatusBar() {
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [feed, setFeed] = useState(null);
  useEffect(() => {
    let cancel = false;
    const load = async () => {
      try {
        const [{ data: ps }, { data: h }, { data: f }] = await Promise.all([
          api.get("/parquet/status"),
          api.get("/health"),
          api.get("/market/feed-status"),
        ]);
        if (!cancel) { setStats(ps); setHealth(h); setFeed(f); }
      } catch (e) { console.error("api fetch failed:", e); }
    };
    load();
    const i = setInterval(load, 3000);
    return () => { cancel = true; clearInterval(i); };
  }, []);

  const isLive = feed && feed.source && feed.source !== "synthetic";
  const sourceLabel = isLive ? (feed.source || "").toUpperCase() : "SYNTHETIC";

  return (
    <div className="flex-1 flex items-center justify-between gap-6 mono text-[11px]" data-testid="status-bar">
      <div className="flex items-center gap-4">
        <span><span className={health?.ticks_running ? "buy" : "sell"}>●</span> TICK·{health?.ticks_running ? "RUNNING" : "STOPPED"}</span>
        <span className="dim">·</span>
        <span data-testid="status-feed-source"><span className={isLive ? "buy" : "warn"}>●</span> FEED·{sourceLabel}{isLive ? ` · ${feed.live_symbol_count}/50` : ""}</span>
        <span className="dim">·</span>
        <span><span className={stats?.running ? "buy" : "sell"}>●</span> PARQUET·{stats?.running ? "RUNNING" : "STOPPED"} {stats?.interval_seconds}s</span>
        <span className="dim">·</span>
        <span data-testid="status-rows-written">ROWS WRITTEN: {fmtInt(stats?.rows_written || 0)}</span>
        <span className="dim">·</span>
        <span>LAST FLUSH: {stats?.last_flush ? new Date(stats.last_flush).toLocaleTimeString("en-IN", { hour12: false }) : "—"}</span>
      </div>
      <div className="flex items-center gap-4">
        <span className="dim">NIFTY · 50</span>
        <span className="dim">{new Date().toLocaleTimeString("en-IN", { hour12: false })} IST</span>
      </div>
    </div>
  );
}
