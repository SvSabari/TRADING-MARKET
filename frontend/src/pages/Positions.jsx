import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtInt, fmtNum, fmtRupee } from "@/lib/format";
import Panel from "@/components/Panel";
import StatTile from "@/components/StatTile";

export default function Positions() {
  const [pos, setPos] = useState([]);
  const [pnl, setPnl] = useState(null);
  useEffect(() => {
    let cancel = false;
    const load = async () => {
      try {
        const [a, b] = await Promise.all([api.get("/orders/positions"), api.get("/orders/pnl-summary")]);
        if (cancel) return;
        setPos(a.data.positions); setPnl(b.data);
      } catch (e) { console.error("api fetch failed:", e); }
    };
    load();
    const i = setInterval(load, 2000);
    return () => { cancel = true; clearInterval(i); };
  }, []);

  return (
    <div className="space-y-4" data-testid="positions-page">
      <div>
        <h1 style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 28, letterSpacing: "-0.02em" }}>Positions.</h1>
        <p className="dim text-sm mt-1">Live mark-to-market on every position. P&L recomputed every 2s.</p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-[#222]">
        <StatTile label="Total P&L" value={fmtRupee(pnl?.total_pnl || 0)} accent={(pnl?.total_pnl || 0) >= 0 ? "buy" : "sell"} big testid="pos-pnl-total" />
        <StatTile label="Unrealized" value={fmtRupee(pnl?.unrealized_pnl || 0)} accent={(pnl?.unrealized_pnl || 0) >= 0 ? "buy" : "sell"} testid="pos-pnl-unrealized" />
        <StatTile label="Realized" value={fmtRupee(pnl?.realized_pnl || 0)} testid="pos-pnl-realized" />
        <StatTile label="Open positions" value={fmtInt(pos.length)} testid="pos-count" />
      </div>

      <Panel title="Open positions" kicker={`${pos.length} symbols`}>
        <table className="w-full text-xs">
          <thead><tr className="dim text-[10px] uppercase tracking-widest border-b border-[#222]">
            <th className="text-left py-2 px-4">Symbol</th>
            <th className="text-right py-2 px-4">Qty</th>
            <th className="text-right py-2 px-4">Avg</th>
            <th className="text-right py-2 px-4">LTP</th>
            <th className="text-right py-2 px-4">P&L</th>
            <th className="text-left py-2 px-4">Side</th>
          </tr></thead>
          <tbody className="cell-divider">
            {pos.map((p) => (
              <tr key={p.id} data-testid={`position-${p.symbol}`}>
                <td className="py-2 px-4 mono">{p.symbol}</td>
                <td className="py-2 px-4 text-right num">{fmtInt(p.qty)}</td>
                <td className="py-2 px-4 text-right num">{fmtNum(p.avg_price)}</td>
                <td className="py-2 px-4 text-right num">{fmtNum(p.last_price)}</td>
                <td className={`py-2 px-4 text-right num ${p.pnl >= 0 ? "buy" : "sell"}`}>{fmtRupee(p.pnl)}</td>
                <td className={`py-2 px-4 mono ${p.qty > 0 ? "buy" : "sell"}`}>{p.qty > 0 ? "LONG" : "SHORT"}</td>
              </tr>
            ))}
            {pos.length === 0 && <tr><td colSpan={6} className="p-8 text-center dim text-xs">No open positions. Fire a TradingView alert or place a manual order.</td></tr>}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
