import { fmtInt, fmtNum, fmtPct } from "@/lib/format";

export default function MoversTable({ rows, title, kicker, accent, testid }) {
  return (
    <div className="panel" data-testid={testid}>
      <div className="panel-h"><span>{title}</span><span className="kicker">· {kicker}</span></div>
      <table className="w-full text-xs">
        <thead><tr className="dim text-[10px] uppercase tracking-widest">
          <th className="text-left py-2 px-4">Symbol</th>
          <th className="text-right py-2 px-4">LTP</th>
          <th className="text-right py-2 px-4">Chg %</th>
          <th className="text-right py-2 px-4">Vol</th>
        </tr></thead>
        <tbody className="cell-divider">
          {rows.map((t) => (
            <tr key={t.symbol} data-testid={`${testid}-${t.symbol}`}>
              <td className="py-2 px-4 mono">{t.symbol}</td>
              <td className="py-2 px-4 text-right num">{fmtNum(t.ltp)}</td>
              <td className={`py-2 px-4 text-right num ${accent}`}>{fmtPct(t.change_pct)}</td>
              <td className="py-2 px-4 text-right num dim">{fmtInt(t.volume)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
