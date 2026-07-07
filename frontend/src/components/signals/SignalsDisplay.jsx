import { useMemo } from "react";
import { fmtNum } from "@/lib/format";

const SIGNAL_CONFIG = {
  long_buildup: { label: "Long Buildup", color: "#00E676", bg: "rgba(0, 230, 118, 0.1)", icon: "↗", desc: "Uptrend with strong volume" },
  short_buildup: { label: "Short Buildup", color: "#FF3B30", bg: "rgba(255, 59, 48, 0.1)", icon: "↙", desc: "Downtrend with strong volume" },
  bull_trap: { label: "Bull Trap", color: "#FFD60A", bg: "rgba(255, 214, 10, 0.1)", icon: "⚠", desc: "Fake breakup on low volume" },
  bear_trap: { label: "Bear Trap", color: "#FF9500", bg: "rgba(255, 149, 0, 0.1)", icon: "⚠", desc: "Fake breakdown on low volume" },
  breakout: { label: "Breakout", color: "#0096FF", bg: "rgba(0, 150, 255, 0.1)", icon: "⬆", desc: "Price beyond 1.8 std dev" },
  reversal: { label: "Reversal", color: "#FF2D55", bg: "rgba(255, 45, 85, 0.1)", icon: "⟲", desc: "Price mean reversion signal" },
};

export default function SignalsDisplay({ signals = [] }) {
  const niftySignal = useMemo(() => {
    return signals.find((s) => s.symbol === "NIFTY 50") || signals[0];
  }, [signals]);

  if (!niftySignal) {
    return (
      <div className="dim text-sm p-4">
        No active signals detected
      </div>
    );
  }

  const cfg = SIGNAL_CONFIG[niftySignal.kind] || {};
  const isLong = ["long_buildup", "breakout", "bull_trap"].includes(niftySignal.kind);
  const isShort = ["short_buildup", "reversal", "bear_trap"].includes(niftySignal.kind);

  return (
    <div className="space-y-4">
      {/* Main Signal Card */}
      <div
        style={{ borderColor: cfg.color, backgroundColor: cfg.bg }}
        className="border-l-4 p-4 rounded-md"
      >
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span style={{ color: cfg.color, fontSize: 18 }}>{cfg.icon}</span>
              <h3 style={{ color: cfg.color, fontWeight: 600 }} className="text-lg">
                {cfg.label}
              </h3>
              <span
                style={{ color: cfg.color, opacity: 0.8 }}
                className="text-xs px-2 py-1 rounded"
              >
                Confidence: {fmtNum(niftySignal.confidence * 100, 0)}%
              </span>
            </div>
            <p className="dim text-xs mt-1">{cfg.desc}</p>
          </div>
          <div className="text-right">
            <div style={{ color: cfg.color }} className="mono text-lg font-bold">
              {fmtNum(niftySignal.price, 2)}
            </div>
            <div
              className="mono text-xs mt-1"
              style={{ color: niftySignal.change_pct > 0 ? "#00E676" : "#FF3B30" }}
            >
              {niftySignal.change_pct > 0 ? "+" : ""}{fmtNum(niftySignal.change_pct, 3)}%
            </div>
          </div>
        </div>

        {/* Metrics Row */}
        <div className="grid grid-cols-3 gap-3 mt-3 text-xs">
          <div className="p-2 bg-black/30 rounded">
            <div className="dim">Vol Ratio</div>
            <div style={{ color: cfg.color }} className="mono font-bold">
              {fmtNum(niftySignal.volume_ratio, 2)}x
            </div>
          </div>
          <div className="p-2 bg-black/30 rounded">
            <div className="dim">Change</div>
            <div
              style={{ color: niftySignal.change_pct > 0 ? "#00E676" : "#FF3B30" }}
              className="mono font-bold"
            >
              {niftySignal.change_pct > 0 ? "+" : ""}{fmtNum(niftySignal.change_pct, 2)}%
            </div>
          </div>
          <div className="p-2 bg-black/30 rounded">
            <div className="dim">Confidence</div>
            <div
              style={{
                color: niftySignal.confidence > 0.8 ? "#00E676" : niftySignal.confidence > 0.6 ? "#FFD60A" : "#FF3B30",
              }}
              className="mono font-bold"
            >
              {fmtNum(niftySignal.confidence, 2)}
            </div>
          </div>
        </div>

        {/* Action Button */}
        <div className="mt-4 flex gap-2">
          {isLong && (
            <button className="flex-1 px-3 py-2 bg-green-900/40 text-green-400 text-xs rounded border border-green-700 hover:bg-green-900/60 transition">
              → BUY LONG
            </button>
          )}
          {isShort && (
            <button className="flex-1 px-3 py-2 bg-red-900/40 text-red-400 text-xs rounded border border-red-700 hover:bg-red-900/60 transition">
              ← SHORT SELL
            </button>
          )}
          <button className="flex-1 px-3 py-2 bg-gray-900/40 text-gray-400 text-xs rounded border border-gray-700 hover:bg-gray-900/60 transition">
            Short Covering
          </button>
          <button className="flex-1 px-3 py-2 bg-gray-900/40 text-gray-400 text-xs rounded border border-gray-700 hover:bg-gray-900/60 transition">
            Long Covering
          </button>
        </div>
      </div>

      {/* All Signals List */}
      {signals.length > 1 && (
        <div className="bg-black/20 rounded-md p-4">
          <h4 className="dim text-xs font-bold mb-3">ALL SIGNALS ({signals.length})</h4>
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {signals.map((sig, idx) => {
              const sigCfg = SIGNAL_CONFIG[sig.kind] || {};
              return (
                <div key={idx} className="flex items-center justify-between text-xs p-2 bg-black/30 rounded">
                  <div className="flex items-center gap-2">
                    <span style={{ color: sigCfg.color }}>{sigCfg.icon}</span>
                    <span className="mono">{sig.symbol}</span>
                    <span style={{ color: sigCfg.color }} className="font-bold">
                      {sigCfg.label}
                    </span>
                  </div>
                  <div className="flex gap-2 items-center">
                    <span className="dim">{fmtNum(sig.price, 2)}</span>
                    <span
                      style={{
                        color:
                          sig.confidence > 0.8 ? "#00E676" : sig.confidence > 0.6 ? "#FFD60A" : "#FF3B30",
                      }}
                    >
                      {fmtNum(sig.confidence, 2)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
