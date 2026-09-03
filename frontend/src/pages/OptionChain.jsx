import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/use-polling";
import { fmtNum } from "@/lib/format";
import Panel from "@/components/Panel";
import StatTile from "@/components/StatTile";
import { OIHeatmapChart, MACDChart } from "@/components/charts/OptionChainCharts";
import ChainTable, { GreeksGrid } from "@/components/options/ChainTable";
import StrategyBuilderPanel from "@/components/StrategyBuilderPanel";

export default function OptionChain() {
  const [symbol, setSymbol] = useState("NIFTY");
  const [expiry, setExpiry] = useState("");
  const [equities, setEquities] = useState([]);
  const [indices, setIndices] = useState(["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "NIFTYNXT50"]);
  const [strategyMode, setStrategyMode] = useState(false);
  const [strategyLegs, setStrategyLegs] = useState([]);

  useEffect(() => {
    api.get("/market/symbols").then(({ data }) => {
      const eqs = data.nifty50 || [];
      const inds = (data.symbols || []).filter((s) => !eqs.includes(s));
      if (eqs.length) setEquities(eqs);
      if (inds.length) setIndices(inds);
    }).catch(console.error);
  }, []);

  const { data: chain, isValidating } = usePolling(`/analytics/option-chain?symbol=${symbol}${expiry ? `&expiry=${expiry}` : ''}`, { intervalMs: 3000 });
  const { data: historyRes } = usePolling(`/market/history/${symbol}`, { intervalMs: 5000 });
  
  // Reset expiry when symbol changes
  useEffect(() => {
    setExpiry("");
  }, [symbol]);

  const heat = chain ? { data: chain.rows.map(r => ({ strike: r.strike, ce_oi: r.ce_oi, pe_oi: r.pe_oi })) } : null;

  if (!chain) return <div className="dim text-sm">Loading option chain…</div>;

  const atmRow = chain.rows.find((r) => r.strike === chain.atm) || chain.rows[Math.floor(chain.rows.length / 2)];

  const totalPreviousOi = chain.rows.reduce((acc, r) => acc + (r.ce_oi - r.ce_change_oi) + (r.pe_oi - r.pe_change_oi), 0);
  const totalChangeOi = chain.rows.reduce((acc, r) => acc + r.ce_change_oi + r.pe_change_oi, 0);
  const totalOiChangePct = totalPreviousOi > 0 ? (totalChangeOi / totalPreviousOi) * 100 : 0;

  return (
    <div className={`space-y-4 transition-opacity duration-200 ${isValidating ? 'opacity-50 pointer-events-none' : 'opacity-100'}`} data-testid="option-chain-page">
      <div>
        <div className="flex flex-wrap items-center gap-4 mb-1">
          <h1 className="whitespace-nowrap" style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 28, letterSpacing: "-0.02em" }}>Option chain</h1>
          <select 
            value={indices.includes(symbol) ? "" : symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="terminal !w-32 cursor-pointer !py-2"
          >
            <option disabled value="" className="bg-white text-gray-500">Equities</option>
            {equities.map((s) => <option key={s} value={s} className="bg-white text-black">{s}</option>)}
          </select>
          <select 
            value={indices.includes(symbol) ? symbol : ""}
            onChange={(e) => setSymbol(e.target.value)}
            className="terminal !w-36 cursor-pointer !py-2"
          >
            <option disabled value="" className="bg-white text-gray-500">Indices</option>
            {indices.map((s) => <option key={s} value={s} className="bg-white text-black">{s}</option>)}
          </select>
          {chain.available_expiries && chain.available_expiries.length > 0 && (
            <select
              value={chain.expiry}
              onChange={(e) => setExpiry(e.target.value)}
              className="terminal !w-40 cursor-pointer !py-2"
            >
              {chain.available_expiries.map((exp) => (
                <option key={exp} value={exp} className="bg-white text-black">{exp}</option>
              ))}
            </select>
          )}
          
          <label className="flex items-center gap-2 cursor-pointer ml-auto bg-blue-50 text-blue-700 px-3 py-1.5 rounded-full border border-blue-200 hover:bg-blue-100 transition-colors">
            <input
              type="checkbox"
              checked={strategyMode}
              onChange={(e) => setStrategyMode(e.target.checked)}
              className="accent-blue-600"
            />
            <span className="text-sm font-bold">Strategy Builder</span>
          </label>
        </div>
        <p className="dim text-sm mt-1">Live PCR, Max Pain, OI heat-strip, IV smile (Black-Scholes Newton-Raphson) and per-strike Greeks. Source: <span className="mono buy">{chain.source === "synthetic" ? "offline" : (chain.source || "offline")}</span></p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <StatTile label={`${symbol} spot`} value={fmtNum(chain.spot)} testid="oc-spot" big />
        <StatTile label="ATM strike" value={fmtNum(chain.atm, 0)} testid="oc-atm" big />
        <StatTile label="PCR" value={fmtNum(chain.pcr, 3)} accent={chain.pcr >= 1 ? "buy" : "sell"} testid="oc-pcr" />
        <StatTile label="Max pain" value={fmtNum(chain.max_pain, 0)} testid="oc-maxpain" />
        <StatTile label="Total OI Chg" value={`${totalOiChangePct > 0 ? '+' : ''}${totalOiChangePct.toFixed(2)}%`} accent={totalOiChangePct > 0 ? "buy" : totalOiChangePct < 0 ? "sell" : ""} testid="oc-oichg" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="OI heatmap" kicker="CE vs PE"><OIHeatmapChart data={heat?.data || []} /></Panel>
        <Panel title="MACD" kicker="momentum & trend"><MACDChart history={historyRes?.candles || []} /></Panel>
      </div>

      {strategyMode && (
        <StrategyBuilderPanel 
          legs={strategyLegs} 
          onRemoveLeg={(idx) => setStrategyLegs(strategyLegs.filter((_, i) => i !== idx))}
          onClear={() => setStrategyLegs([])}
        />
      )}

      <Panel title="Option chain" kicker="ATM ± 15 strikes">
        <ChainTable 
          chain={chain} 
          strategyMode={strategyMode} 
          onAddLeg={(leg) => setStrategyLegs([...strategyLegs, leg])} 
        />
      </Panel>

      <Panel title={`Greeks @ ATM ${chain.atm}`} kicker="Black-Scholes · risk-free 7%">
        <GreeksGrid row={atmRow} />
      </Panel>
    </div>
  );
}
