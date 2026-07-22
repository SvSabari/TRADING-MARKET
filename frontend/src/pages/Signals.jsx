import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtNum, fmtPct, fmtTime } from "@/lib/format";
import Panel from "@/components/Panel";
import SignalExplainModal from "@/components/SignalExplainModal";
import { Brain } from "@phosphor-icons/react";

const KIND_COLOR = {
  long_buildup: "buy", short_buildup: "sell",
  breakout: "buy", breakdown: "sell",
  bull_trap: "warn", bear_trap: "warn",
};

export default function Signals() {
  const [signals, setSignals] = useState([]);
  const [explain, setExplain] = useState(null);

  useEffect(() => {
    let cancel = false;
    const load = async () => {
      try { const { data } = await api.get("/signals/live"); if (!cancel) setSignals(data.signals); } catch (e) { console.error("api fetch failed:", e); }
    };
    load();
    const i = setInterval(load, 2000);
    return () => { cancel = true; clearInterval(i); };
  }, []);

  return (
    <div className="space-y-4" data-testid="signals-page">
      <div>
        <h1 style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 28, letterSpacing: "-0.02em" }}>Signal engine.</h1>
        <p className="dim text-sm mt-1">Build-ups, traps, breakouts and reversals — computed on the live 1-second tick history. Tap the brain icon for Claude&apos;s reasoning + suggested SL/target.</p>
      </div>
      <Panel title="Active signals" kicker={`${signals.length} detected`}>
        <table className="w-full text-xs">
          <thead>
            <tr className="dim text-[10px] uppercase tracking-widest border-b border-[#222]">
              <th className="text-left py-2 px-4">Time</th>
              <th className="text-left py-2 px-4">Kind</th>
              <th className="text-left py-2 px-4">Symbol</th>
              <th className="text-right py-2 px-4">Price</th>
              <th className="text-right py-2 px-4">Δ %</th>
              <th className="text-right py-2 px-4">Vol ratio</th>
              <th className="text-right py-2 px-4">Confidence</th>
              <th className="text-right py-2 px-4">AI</th>
            </tr>
          </thead>
          <tbody className="cell-divider">
            {signals.length === 0 && (
              <tr><td colSpan={8} className="p-8 text-center dim text-xs">No signals yet — waiting for confluence.</td></tr>
            )}
            {signals.map((s) => (
              <tr key={`${s.symbol}-${s.kind}-${s.ts}`} data-testid={`signal-${s.symbol}-${s.kind}`}>
                <td className="py-2 px-4 mono dim">{fmtTime(s.ts)}</td>
                <td className={`py-2 px-4 mono ${KIND_COLOR[s.kind] || ""}`}>{s.kind.replace("_", " ").toUpperCase()}</td>
                <td className="py-2 px-4 mono">{s.symbol}</td>
                <td className="py-2 px-4 text-right num">{fmtNum(s.price)}</td>
                <td className={`py-2 px-4 text-right num ${s.change_pct >= 0 ? "buy" : "sell"}`}>{fmtPct(s.change_pct)}</td>
                <td className="py-2 px-4 text-right num dim">{fmtNum(s.volume_ratio)}×</td>
                <td className="py-2 px-4 text-right num">
                  <div className="inline-flex items-center gap-2">
                    <div className="w-16 h-1 bg-[#222]">
                      <div className={`h-1 ${s.confidence > 0.75 ? "bg-[#00E676]" : s.confidence > 0.6 ? "bg-[#FFD60A]" : "bg-[#FF3B30]"}`} style={{ width: `${s.confidence * 100}%` }} />
                    </div>
                    {(s.confidence * 100).toFixed(0)}%
                  </div>
                </td>
                <td className="py-2 px-4 text-right">
                  <button
                    data-testid={`signal-explain-${s.symbol}`}
                    onClick={() => setExplain(s)}
                    className="dim hover:text-[#00E676] transition-colors p-1"
                    title="Explain with Claude"
                  >
                    <Brain size={14} weight="bold" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
      {explain && <SignalExplainModal signal={explain} onClose={() => setExplain(null)} />}
    </div>
  );
}
