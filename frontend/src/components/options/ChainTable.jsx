import { fmtInt, fmtNum } from "@/lib/format";

export default function ChainTable({ chain, strategyMode = false, onAddLeg }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="dim text-[10px] uppercase tracking-widest border-b border-[#222]">
            <th className="text-right py-2 px-3" colSpan={4}>CALLS</th>
            <th className="text-center py-2 px-3">STRIKE</th>
            <th className="text-left py-2 px-3" colSpan={4}>PUTS</th>
          </tr>
          <tr className="dim text-[10px] uppercase tracking-widest border-b border-[#222]">
            <th className="text-right py-2 px-3">OI</th>
            <th className="text-right py-2 px-3">CHNG OI</th>
            <th className="text-right py-2 px-3">TREND</th>
            <th className="text-right py-2 px-3">LTP</th>
            <th className="text-center py-2 px-3">—</th>
            <th className="text-left py-2 px-3">LTP</th>
            <th className="text-left py-2 px-3">TREND</th>
            <th className="text-left py-2 px-3">CHNG OI</th>
            <th className="text-left py-2 px-3">OI</th>
          </tr>
        </thead>
        <tbody className="cell-divider">
          {chain.rows.map((r) => {
            const atm = r.strike === chain.atm;
            const formatTrend = (t) => {
              if (t === "Long Buildup") return "BULL TRAP";
              if (t === "Short Buildup") return "BEAR TRAP";
              if (t === "Long Unwinding") return "LONG UNWINDING";
              if (t === "Short Covering") return "SHORT UNWINDING";
              return "NEUTRAL";
            };
            const trendColor = (t) => {
              if (t === "Long Buildup" || t === "Short Covering") return "buy";
              if (t === "Short Buildup" || t === "Long Unwinding") return "sell";
              return "dim";
            };
            return (
              <tr key={r.strike} className={atm ? "bg-gray-200" : ""} data-testid={`oc-row-${r.strike}`}>
                <td className="py-2 px-3 text-right num dim">{fmtInt(r.ce_oi)}</td>
                <td className="py-2 px-3 text-right">
                  <div className="num">{r.ce_change_oi > 0 ? "+" : ""}{fmtInt(r.ce_change_oi)}</div>
                  {r.ce_oi - r.ce_change_oi > 0 && (
                    <div className={`text-[10px] mt-0.5 ${r.ce_change_oi > 0 ? "buy" : r.ce_change_oi < 0 ? "sell" : "dim"}`}>
                      ({r.ce_change_oi > 0 ? "+" : ""}{((r.ce_change_oi / (r.ce_oi - r.ce_change_oi)) * 100).toFixed(1)}%)
                    </div>
                  )}
                </td>
                <td className={`py-2 px-3 text-right text-[10px] uppercase tracking-wider ${trendColor(r.ce_trend)}`}>{formatTrend(r.ce_trend)}</td>
                <td className="py-2 px-3 text-right num group relative">
                  <span className={strategyMode ? "group-hover:opacity-0" : ""}>{fmtNum(r.ce_ltp)}</span>
                  {strategyMode && (
                    <div className="absolute inset-0 flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 pr-2">
                      <button onClick={() => onAddLeg({ type: 'CE', side: 'Buy', strike: r.strike, premium: r.ce_ltp })} className="text-[10px] bg-green-500 text-white px-1.5 py-0.5 rounded">B</button>
                      <button onClick={() => onAddLeg({ type: 'CE', side: 'Sell', strike: r.strike, premium: r.ce_ltp })} className="text-[10px] bg-red-500 text-white px-1.5 py-0.5 rounded">S</button>
                    </div>
                  )}
                </td>
                <td className={`py-2 px-3 text-center num ${atm ? "buy" : ""}`}>{r.strike}</td>
                <td className="py-2 px-3 text-left num group relative">
                  <span className={strategyMode ? "group-hover:opacity-0" : ""}>{fmtNum(r.pe_ltp)}</span>
                  {strategyMode && (
                    <div className="absolute inset-0 flex items-center justify-start gap-1 opacity-0 group-hover:opacity-100 pl-2">
                      <button onClick={() => onAddLeg({ type: 'PE', side: 'Buy', strike: r.strike, premium: r.pe_ltp })} className="text-[10px] bg-green-500 text-white px-1.5 py-0.5 rounded">B</button>
                      <button onClick={() => onAddLeg({ type: 'PE', side: 'Sell', strike: r.strike, premium: r.pe_ltp })} className="text-[10px] bg-red-500 text-white px-1.5 py-0.5 rounded">S</button>
                    </div>
                  )}
                </td>
                <td className={`py-2 px-3 text-left text-[10px] uppercase tracking-wider ${trendColor(r.pe_trend)}`}>{formatTrend(r.pe_trend)}</td>
                <td className="py-2 px-3 text-left">
                  <div className="num">{r.pe_change_oi > 0 ? "+" : ""}{fmtInt(r.pe_change_oi)}</div>
                  {r.pe_oi - r.pe_change_oi > 0 && (
                    <div className={`text-[10px] mt-0.5 ${r.pe_change_oi > 0 ? "buy" : r.pe_change_oi < 0 ? "sell" : "dim"}`}>
                      ({r.pe_change_oi > 0 ? "+" : ""}{((r.pe_change_oi / (r.pe_oi - r.pe_change_oi)) * 100).toFixed(1)}%)
                    </div>
                  )}
                </td>
                <td className="py-2 px-3 text-left num dim">{fmtInt(r.pe_oi)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function GreeksGrid({ row }) {
  const ce = row?.ce_greeks || {}; const pe = row?.pe_greeks || {};
  const cell = (label, c, p, decimals = 4) => (
    <div className="bg-white p-4" key={label}>
      <div className="dim text-[10px] mono uppercase tracking-widest">{label}</div>
      <div className="grid grid-cols-2 gap-2 mt-1">
        <div><span className="dim text-[10px] mono">CE</span> <span className="num text-sm">{c !== undefined ? fmtNum(c, decimals) : "—"}</span></div>
        <div><span className="dim text-[10px] mono">PE</span> <span className="num text-sm">{p !== undefined ? fmtNum(p, decimals) : "—"}</span></div>
      </div>
    </div>
  );
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-px bg-gray-300" data-testid="greeks-grid">
      {cell("Delta", ce.delta, pe.delta, 3)}
      {cell("Gamma", ce.gamma, pe.gamma, 5)}
      {cell("Theta (/day)", ce.theta, pe.theta, 2)}
      {cell("Vega (/1%)", ce.vega, pe.vega, 3)}
      {cell("Rho (/1%)", ce.rho, pe.rho, 3)}
    </div>
  );
}
