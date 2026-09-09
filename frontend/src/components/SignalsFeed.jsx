import { Link } from "react-router-dom";
import { fmtPct } from "@/lib/format";

const KIND_COLOR = (k) =>
  k?.includes("buildup") || k === "breakout" ? "buy"
  : k?.includes("trap") ? "warn" : "sell";

export default function SignalsFeed({ signals }) {
  return (
    <div className="panel" data-testid="signals-feed">
      <div className="panel-h"><span>Live signals</span><span className="kicker">A {signals.length} active</span></div>
      <div className="px-4 py-2 flex items-center justify-between text-[10px] uppercase font-bold text-[var(--text-secondary)] border-b border-[var(--border)]">
        <div className="flex items-center gap-3 w-1/2">
          <span className="w-24">Symbol</span>
          <span>Signal</span>
        </div>
        <div className="flex items-center justify-end gap-3 w-1/2">
          <span className="w-16 text-right">Change</span>
          <span className="w-12 text-right">Conf</span>
        </div>
      </div>
      <div className="cell-divider max-h-[280px] overflow-y-auto">
        {signals.length === 0 && (
          <div className="p-6 dim text-xs mono">No signals yet. Waiting for confluence...</div>
        )}
        {signals.slice(0, 12).map((s) => (
          <div key={`${s.symbol}-${s.kind}-${s.ts}`} className="px-4 py-2 flex items-center justify-between text-xs hover:bg-[var(--surface-hover)] cursor-default transition-colors" data-testid={`signal-row-${s.symbol}-${s.kind}`}>
            <div className="flex items-center gap-3 w-1/2">
              <span className="mono font-bold w-24 truncate text-[var(--text-primary)]">{s.symbol}</span>
              <span className={`mono ${KIND_COLOR(s.kind)}`}>{s.kind.replace("_", " ").toUpperCase()}</span>
            </div>
            <div className="flex items-center justify-end gap-3 w-1/2">
              <span className={`num w-16 text-right ${s.change_pct >= 0 ? "buy" : "sell"}`}>{fmtPct(s.change_pct)}</span>
              <span className="num dim w-12 text-right">{(s.confidence * 100).toFixed(0)}%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
