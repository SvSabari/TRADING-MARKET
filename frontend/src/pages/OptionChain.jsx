import { useState } from "react";
import { usePolling } from "@/lib/use-polling";
import { fmtNum } from "@/lib/format";
import Panel from "@/components/Panel";
import StatTile from "@/components/StatTile";
import { OIHeatmapChart, IVSmileChart } from "@/components/charts/OptionChainCharts";
import ChainTable, { GreeksGrid } from "@/components/options/ChainTable";

export default function OptionChain() {
  const [symbol, setSymbol] = useState("NIFTY");
  const { data: chain } = usePolling(`/analytics/option-chain?symbol=${symbol}`, { intervalMs: 3000 });
  const { data: heat } = usePolling(`/analytics/oi-heatmap?symbol=${symbol}`, { intervalMs: 3000 });
  const { data: smile } = usePolling(`/analytics/iv-smile?symbol=${symbol}`, { intervalMs: 3000 });

  if (!chain) return <div className="dim text-sm">Loading option chain…</div>;

  const atmRow = chain.rows.find((r) => r.strike === chain.atm) || chain.rows[Math.floor(chain.rows.length / 2)];

  return (
    <div className="space-y-4" data-testid="option-chain-page">
      <div>
        <div className="flex items-center gap-3">
          <h1 style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 28, letterSpacing: "-0.02em" }}>Option chain · </h1>
          <select 
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="bg-transparent text-white outline-none cursor-pointer hover:text-white/80 transition-colors"
            style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 28, letterSpacing: "-0.02em" }}
          >
            <option value="NIFTY" className="bg-[#111] text-base font-normal">NIFTY</option>
            <option value="BANKNIFTY" className="bg-[#111] text-base font-normal">BANKNIFTY</option>
            <option value="FINNIFTY" className="bg-[#111] text-base font-normal">FINNIFTY</option>
            <option value="MIDCPNIFTY" className="bg-[#111] text-base font-normal">MIDCPNIFTY</option>
          </select>
        </div>
        <p className="dim text-sm mt-1">Live PCR, Max Pain, OI heat-strip, IV smile (Black-Scholes Newton-Raphson) and per-strike Greeks. Source: <span className="mono buy">{chain.source || "synthetic"}</span></p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-[#222]">
        <StatTile label={`${symbol} spot`} value={fmtNum(chain.spot)} testid="oc-spot" big />
        <StatTile label="ATM strike" value={fmtNum(chain.atm, 0)} testid="oc-atm" big />
        <StatTile label="PCR" value={fmtNum(chain.pcr, 3)} accent={chain.pcr >= 1 ? "buy" : "sell"} testid="oc-pcr" />
        <StatTile label="Max pain" value={fmtNum(chain.max_pain, 0)} accent="warn" testid="oc-maxpain" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="OI heatmap" kicker="CE vs PE"><OIHeatmapChart data={heat?.data || []} /></Panel>
        <Panel title="IV smile" kicker="implied vol per strike"><IVSmileChart data={smile?.data || []} /></Panel>
      </div>

      <Panel title="Option chain" kicker="ATM ± 15 strikes">
        <ChainTable chain={chain} />
      </Panel>

      <Panel title={`Greeks @ ATM ${chain.atm}`} kicker="Black-Scholes · risk-free 7%">
        <GreeksGrid row={atmRow} />
      </Panel>
    </div>
  );
}
