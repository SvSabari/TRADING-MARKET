import { Link } from "react-router-dom";
import { fmtPct } from "@/lib/format";

const KIND_COLOR = (k) =>
  k?.includes("buildup") || k === "breakout" ? "buy"
  : k?.includes("trap") ? "warn" : "sell";

export default function SignalsFeed({ signals }) {
  return (
    <div className="panel" data-testid="signals-feed">
      <div className="panel-h"><span>Live signals</span><span className="kicker">· {signals.length} active</span></div>
      <div className="cell-divider max-h-[280px] overflow-y-auto">
        {signals.length === 0 && (
          <div className="p-6 dim text-xs mono">No signals yet. Waiting for confluence…</div>
        )}
        {signals.slice(0, 12).map((s) => (
          <div key={`${s.symbol}-${s.kind}-${s.ts}`} className="px-4 py-2 flex items-center justify-between text-xs" data-testid={`signal-row-${s.symbol}-${s.kind}`}>
            <div className="flex items-center gap-3">
              <span className={`mono ${KIND_COLOR(s.kind)}`}>{s.kind.replace("_", " ").toUpperCase()}</span>
              <span className="mono">{s.symbol}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className={`num ${s.change_pct >= 0 ? "buy" : "sell"}`}>{fmtPct(s.change_pct)}</span>
              <span className="num dim">{(s.confidence * 100).toFixed(0)}%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
