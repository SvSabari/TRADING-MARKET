import { fmtInt, fmtNum } from "@/lib/format";

export default function ChainTable({ chain }) {
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
            <th className="text-right py-2 px-3">Δ</th>
            <th className="text-right py-2 px-3">IV</th>
            <th className="text-right py-2 px-3">LTP</th>
            <th className="text-center py-2 px-3">—</th>
            <th className="text-left py-2 px-3">LTP</th>
            <th className="text-left py-2 px-3">IV</th>
            <th className="text-left py-2 px-3">Δ</th>
            <th className="text-left py-2 px-3">OI</th>
          </tr>
        </thead>
        <tbody className="cell-divider">
          {chain.rows.map((r) => {
            const atm = r.strike === chain.atm;
            const ceDelta = r.ce_greeks?.delta;
            const peDelta = r.pe_greeks?.delta;
            return (
              <tr key={r.strike} className={atm ? "bg-[#1A1A1A]" : ""} data-testid={`oc-row-${r.strike}`}>
                <td className="py-2 px-3 text-right num dim">{fmtInt(r.ce_oi)}</td>
                <td className="py-2 px-3 text-right num dim">{ceDelta !== undefined ? fmtNum(ceDelta, 3) : "—"}</td>
                <td className="py-2 px-3 text-right num dim">{fmtNum(r.ce_iv)}</td>
                <td className="py-2 px-3 text-right num">{fmtNum(r.ce_ltp)}</td>
                <td className={`py-2 px-3 text-center num ${atm ? "buy" : ""}`}>{r.strike}</td>
                <td className="py-2 px-3 text-left num">{fmtNum(r.pe_ltp)}</td>
                <td className="py-2 px-3 text-left num dim">{fmtNum(r.pe_iv)}</td>
                <td className="py-2 px-3 text-left num dim">{peDelta !== undefined ? fmtNum(peDelta, 3) : "—"}</td>
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
    <div className="bg-[#121212] p-4" key={label}>
      <div className="dim text-[10px] mono uppercase tracking-widest">{label}</div>
      <div className="grid grid-cols-2 gap-2 mt-1">
        <div><span className="dim text-[10px] mono">CE</span> <span className="num text-sm">{c !== undefined ? fmtNum(c, decimals) : "—"}</span></div>
        <div><span className="dim text-[10px] mono">PE</span> <span className="num text-sm">{p !== undefined ? fmtNum(p, decimals) : "—"}</span></div>
      </div>
    </div>
  );
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-px bg-[#222]" data-testid="greeks-grid">
      {cell("Delta", ce.delta, pe.delta, 3)}
      {cell("Gamma", ce.gamma, pe.gamma, 5)}
      {cell("Theta (/day)", ce.theta, pe.theta, 2)}
      {cell("Vega (/1%)", ce.vega, pe.vega, 3)}
      {cell("Rho (/1%)", ce.rho, pe.rho, 3)}
    </div>
  );
}
