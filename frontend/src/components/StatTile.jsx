import { fmtNum, fmtPct } from "@/lib/format";

export default function StatTile({ label, value, delta, accent, testid, big }) {
  const color = accent === "buy" ? "buy" : accent === "sell" ? "sell" : "";
  return (
    <div className="panel p-4 flex flex-col gap-2 overflow-hidden" data-testid={testid}>
      <div className="dim text-[10px] uppercase tracking-widest font-mono truncate" title={label}>{label}</div>
      <div className={`num ${color} tracking-tight truncate`} style={{ fontSize: big ? 'clamp(20px, 2vw, 28px)' : 22, lineHeight: 1, fontWeight: 700 }} title={value}>
        {value}
      </div>
      {delta !== undefined && delta !== null && (
        <div className={`num text-xs ${delta >= 0 ? "buy" : "sell"}`}>{fmtPct(delta, 2)}</div>
      )}
    </div>
  );
}
