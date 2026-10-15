import { useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/use-polling";
import { fmtNum } from "@/lib/format";
import Panel from "@/components/Panel";

export default function PremiumMatcher({ preset, showSymbolColumn }) {
  const [rangeSize, setRangeSize] = useState(10);
  const [maxDiff, setMaxDiff] = useState(50);
  const [trackedPairs, setTrackedPairs] = useState([]);
  const [isOrdering, setIsOrdering] = useState(false);

  const trackedSymbolsQuery = trackedPairs.map(t => `${t.symbol}_${t.callStrike}_CE,${t.symbol}_${t.putStrike}_PE`).join(',');
  
  const { data, isValidating } = usePolling(
    `/analytics/premium-matcher?preset=${preset}&range_size=${rangeSize}&max_diff=${maxDiff}&tracked=${trackedSymbolsQuery}`,
    { intervalMs: 3000 }
  );

  const pairs = data?.matches || [];
  const trackedPrices = data?.tracked_prices || {};

  const handleBuy = async (pair) => {
    setIsOrdering(true);
    try {
      const payloadCE = {
        symbol: `${pair.symbol}_${pair.callStrike}_CE`,
        side: "BUY",
        qty: 1,
        price: pair.callLtp,
      };
      
      const payloadPE = {
        symbol: `${pair.symbol}_${pair.putStrike}_PE`,
        side: "BUY",
        qty: 1,
        price: pair.putLtp,
      };

      await api.post("/orders", payloadCE);
      await api.post("/orders", payloadPE);

      toast.success(`Bought Strangle: ${pair.callStrike} CE & ${pair.putStrike} PE for ${pair.symbol}`);
      
      setTrackedPairs(prev => [
        {
          id: Date.now(),
          symbol: pair.symbol,
          callStrike: pair.callStrike,
          buyCallLtp: pair.callLtp,
          putStrike: pair.putStrike,
          buyPutLtp: pair.putLtp,
          timestamp: new Date().toLocaleTimeString()
        },
        ...prev
      ]);
    } catch (e) {
      toast.error("Failed to place orders");
    } finally {
      setIsOrdering(false);
    }
  };

  const getTrackedLivePnl = (t) => {
    const ceSym = `${t.symbol}_${t.callStrike}_CE`;
    const peSym = `${t.symbol}_${t.putStrike}_PE`;
    
    const currCall = trackedPrices[ceSym] || t.buyCallLtp;
    const currPut = trackedPrices[peSym] || t.buyPutLtp;

    const callPnl = currCall - t.buyCallLtp;
    const putPnl = currPut - t.buyPutLtp;
    
    return {
      callPnl,
      putPnl,
      totalPnl: callPnl + putPnl,
      currCall,
      currPut
    };
  };

  const handleRemoveTracked = (id) => {
    setTrackedPairs(prev => prev.filter(t => t.id !== id));
  };

  return (
    <div className={`space-y-4 transition-opacity duration-200 ${isValidating && pairs.length === 0 ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>
      <Panel 
        title="Premium Comparison Matcher" 
        kicker={preset === "indices" ? "All Indices" : preset === "all" ? "Whole Market" : preset}
        right={
          <div className="flex gap-4">
            <div className="flex items-center gap-2">
              <span className="dim text-xs">Range:</span>
              <select 
                className="terminal !w-auto !py-1 !text-xs"
                value={rangeSize}
                onChange={e => setRangeSize(Number(e.target.value))}
              >
                <option value={5}>+/- 5 Strikes</option>
                <option value={10}>+/- 10 Strikes</option>
                <option value={15}>+/- 15 Strikes</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <span className="dim text-xs">Max Diff:</span>
              <select 
                className="terminal !w-auto !py-1 !text-xs"
                value={maxDiff}
                onChange={e => setMaxDiff(Number(e.target.value))}
              >
                <option value={2}>&lt;= 2.0</option>
                <option value={5}>&lt;= 5.0</option>
                <option value={10}>&lt;= 10.0</option>
                <option value={20}>&lt;= 20.0</option>
                <option value={50}>&lt;= 50.0</option>
                <option value={100}>&lt;= 100.0</option>
                <option value={200}>&lt;= 200.0</option>
              </select>
            </div>
          </div>
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-[#333] text-xs dim">
                {showSymbolColumn && <th className="p-2 font-normal">SYMBOL</th>}
                <th className="p-2 font-normal">TYPE</th>
                <th className="p-2 font-normal">CURRENT PRICE</th>
                <th className="p-2 font-normal">CALL STRIKE</th>
                <th className="p-2 font-normal">CALL LTP</th>
                <th className="p-2 font-normal">PUT STRIKE</th>
                <th className="p-2 font-normal">PUT LTP</th>
                <th className="p-2 font-normal">DIFFERENCE</th>
                <th className="p-2 font-normal text-right">ACTION</th>
              </tr>
            </thead>
            <tbody>
              {!data ? (
                <tr>
                  <td colSpan={showSymbolColumn ? 8 : 7} className="p-4 text-center dim text-sm">
                    Loading premium pairs...
                  </td>
                </tr>
              ) : pairs.length === 0 ? (
                <tr>
                  <td colSpan={showSymbolColumn ? 9 : 8} className="p-4 text-center dim text-sm">
                    No matching pairs found in this range. (Ensure broker session is connected for live option quotes)
                  </td>
                </tr>
              ) : (
                pairs.map((p, idx) => (
                  <tr key={`${p.symbol}-${p.callStrike}-${p.putStrike}-${idx}`} className="border-b border-[var(--border)] bg-[#181C27] hover:bg-[#1E222D] transition-colors">
                    {showSymbolColumn && <td className="p-2 text-sm mono font-bold text-[var(--brand)]">{p.symbol}</td>}
                    <td className="p-2">
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${p.type === "straddle" ? "bg-blue-500/20 text-blue-400 border border-blue-500/30" : "bg-amber-500/20 text-amber-400 border border-amber-500/30"}`}>
                        {(p.type || "straddle").toUpperCase()}
                      </span>
                    </td>
                    <td className="p-2 text-sm mono text-[#BAC0D0]">{fmtNum(p.spot)}</td>
                    <td className="p-2 text-sm mono font-semibold text-white">
                      {fmtNum(p.callStrike, 0)}
                    </td>
                    <td className="p-2 text-sm mono buy font-bold">{fmtNum(p.callLtp)}</td>
                    <td className="p-2 text-sm mono font-semibold text-white">
                      {fmtNum(p.putStrike, 0)}
                    </td>
                    <td className="p-2 text-sm mono sell font-bold">{fmtNum(p.putLtp)}</td>
                    <td className="p-2 text-sm mono font-bold" style={{ color: p.diff < 2 ? "#38BDF8" : p.diff < 10 ? "#089981" : "#F59E0B" }}>
                      {fmtNum(p.diff)}
                    </td>
                    <td className="p-2 text-right">
                      <button 
                        onClick={() => handleBuy(p)}
                        disabled={isOrdering}
                        className="px-3 py-1 bg-[var(--brand)] text-white text-xs font-semibold rounded border border-[var(--brand)] hover:bg-[#1E53E5] transition disabled:opacity-50"
                      >
                        Buy Pair
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Panel>

      {trackedPairs.length > 0 && (
        <Panel title="Active Tracked Pairs" kicker="Live PnL">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-[#333] text-xs dim">
                  <th className="p-2 font-normal">TIME</th>
                  <th className="p-2 font-normal">STRATEGY</th>
                  <th className="p-2 font-normal">CALL PNL</th>
                  <th className="p-2 font-normal">PUT PNL</th>
                  <th className="p-2 font-normal text-right">TOTAL PNL</th>
                  <th className="p-2 font-normal text-right">ACTION</th>
                </tr>
              </thead>
              <tbody>
                {trackedPairs.map((t) => {
                  const pnl = getTrackedLivePnl(t);
                  return (
                    <tr key={t.id} className="border-b border-[var(--border)] bg-[#181C27] hover:bg-[#1E222D] transition-colors">
                      <td className="p-2 text-sm text-[#BAC0D0] mono">{t.timestamp}</td>
                      <td className="p-2 text-sm mono font-semibold text-white">
                        {t.symbol} {fmtNum(t.callStrike, 0)}CE + {fmtNum(t.putStrike, 0)}PE
                      </td>
                      <td className={`p-2 text-sm mono font-bold ${pnl.callPnl >= 0 ? "buy" : "sell"}`}>
                        {pnl.callPnl >= 0 ? "+" : ""}{fmtNum(pnl.callPnl)}
                      </td>
                      <td className={`p-2 text-sm mono font-bold ${pnl.putPnl >= 0 ? "buy" : "sell"}`}>
                        {pnl.putPnl >= 0 ? "+" : ""}{fmtNum(pnl.putPnl)}
                      </td>
                      <td className={`p-2 text-sm mono text-right font-bold ${pnl.totalPnl >= 0 ? "buy" : "sell"}`}>
                        {pnl.totalPnl >= 0 ? "+" : ""}{fmtNum(pnl.totalPnl)}
                      </td>
                      <td className="p-2 text-right">
                        <button 
                          onClick={() => handleRemoveTracked(t.id)}
                          className="px-2 py-1 bg-red-900/40 text-red-400 text-xs rounded border border-red-700 hover:bg-red-900/60 transition"
                        >
                          Clear
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  );
}
