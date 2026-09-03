import { useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";
import { fmtInt } from "@/lib/format";
import { getMarketStatus } from "@/lib/marketHours";

export default function StatusBar() {
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [feed, setFeed] = useState(null);
  const [showLive, setShowLive] = useState(false);
  const [mktStatus, setMktStatus] = useState(getMarketStatus());
  const popupRef = useRef(null);

  useEffect(() => {
    const tick = () => setMktStatus(getMarketStatus());
    tick();
    const i = setInterval(tick, 30000);
    return () => clearInterval(i);
  }, []);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (popupRef.current && !popupRef.current.contains(event.target)) {
        setShowLive(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);
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

  const isLive = feed && feed.source && feed.source !== "synthetic" && feed.source !== "none" && feed.source !== "offline";
  const sourceLabel = isLive ? (feed.source || "").toUpperCase() : "OFFLINE";

  return (
    <div className="flex-1 flex items-center justify-between gap-6 mono text-[11px]" data-testid="status-bar">
      <div className="flex items-center gap-4">
        <span><span className={health?.ticks_running ? "buy" : "sell"}>●</span> TICK·{health?.ticks_running ? "RUNNING" : "STOPPED"}</span>
        <span className="dim">·</span>
        <span data-testid="status-feed-source">
          <span className={isLive ? "buy" : "warn"}>●</span> FEED·{sourceLabel}
          {isLive ? (
            <span className="relative" ref={popupRef}>
              <span 
                className="cursor-pointer hover:text-[#2962ff] transition-colors ml-1"
                onClick={() => setShowLive(!showLive)}
              >
                · {feed.live_symbol_count}/56
              </span>
              {showLive && feed.live_symbols && (
                <div className="absolute bottom-full mb-2 left-0 w-56 bg-white border border-gray-300 rounded shadow-2xl z-50 text-left cursor-default overflow-hidden flex flex-col">
                  <div className="text-gray-500 font-bold px-3 py-2 border-b border-gray-300 text-[10px] uppercase tracking-wider bg-gray-100">
                    Live Data Feed ({feed.live_symbol_count})
                  </div>
                  <div className="flex flex-col max-h-64 overflow-y-auto custom-scrollbar">
                    {feed.live_symbols.map(s => (
                      <div key={s} className="px-3 py-2 text-[11px] text-gray-800 hover:bg-gray-100 border-b border-gray-300 last:border-0 transition-colors flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#00E676]"></span>
                        <span className="font-mono">{s}</span>
                      </div>
                    ))}
                    {feed.live_symbol_count === 0 && (
                      <div className="px-3 py-4 text-center text-[#555] text-[10px] italic">No active streams</div>
                    )}
                  </div>
                </div>
              )}
            </span>
          ) : ""}
        </span>
        {feed?.feed?.last_error && (
          <>
            <span className="dim">·</span>
            <span className="sell font-bold animate-pulse truncate max-w-[200px]" title={feed.feed.last_error}>⚠️ BROKER ERROR</span>
          </>
        )}
        <span className="dim">·</span>
        <span><span className={stats?.running ? "buy" : "sell"}>●</span> PARQUET·{stats?.running ? "RUNNING" : "STOPPED"} {stats?.interval_seconds}s</span>
        <span className="dim">·</span>
        <span data-testid="status-rows-written">ROWS WRITTEN: {fmtInt(stats?.rows_written || 0)}</span>
        <span className="dim">·</span>
        <span>LAST FLUSH: {stats?.last_flush ? new Date(stats.last_flush).toLocaleTimeString("en-IN", { hour12: false }) : "—"}</span>
      </div>
      <div className="flex items-center gap-4">
        {!mktStatus.open && (
          <span
            className="font-bold mono uppercase tracking-widest text-[10px] px-2 py-0.5 rounded"
            style={{ background: "rgba(239,68,68,0.12)", color: mktStatus.color, border: `1px solid ${mktStatus.color}40` }}
          >
            ● {mktStatus.label} · LAST PRICES SHOWN
          </span>
        )}
        <span className="dim">ALL SYMBOLS · 56</span>
        <span className="dim">{new Date().toLocaleTimeString("en-IN", { hour12: false })} IST</span>
      </div>
    </div>
  );
}
