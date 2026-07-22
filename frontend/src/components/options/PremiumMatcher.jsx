import { useState, useMemo } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { fmtNum } from "@/lib/format";
import Panel from "@/components/Panel";

export default function PremiumMatcher({ chain, symbol }) {
  const [rangeSize, setRangeSize] = useState(10);
  const [maxDiff, setMaxDiff] = useState(5);
  const [trackedPairs, setTrackedPairs] = useState([]);
  const [isOrdering, setIsOrdering] = useState(false);

  // Compute matched pairs
  const pairs = useMemo(() => {
    if (!chain || !chain.rows || chain.rows.length === 0) return [];

    const atm = chain.atm;
    const sortedRows = [...chain.rows].sort((a, b) => a.strike - b.strike);
    
    // Find index of ATM
    let atmIndex = sortedRows.findIndex(r => r.strike === atm);
    if (atmIndex === -1) {
      // fallback to closest if exact ATM missing
      let minD = Infinity;
      sortedRows.forEach((r, i) => {
        const d = Math.abs(r.strike - atm);
        if (d < minD) {
          minD = d;
          atmIndex = i;
        }
      });
    }

    const startIdx = Math.max(0, atmIndex - rangeSize);
    const endIdx = Math.min(sortedRows.length - 1, atmIndex + rangeSize);
    const rangeContracts = sortedRows.slice(startIdx, endIdx + 1);

    const calls = rangeContracts.filter(r => (r.ce_ltp || 0) >= 2.0);
    const puts = rangeContracts.filter(r => (r.pe_ltp || 0) >= 2.0);

    const matches = [];

    calls.forEach(c => {
      puts.forEach(p => {
        const diff = Math.abs(c.ce_ltp - p.pe_ltp);
        if (diff <= maxDiff) {
          matches.push({
            callStrike: c.strike,
            callLtp: c.ce_ltp,
            putStrike: p.strike,
            putLtp: p.pe_ltp,
            diff: diff,
            isCenter: c.strike === atm
          });
        }
      });
    });

    // Sort by smallest difference first, center strike at top
    matches.sort((a, b) => {
      if (a.isCenter && !b.isCenter) return -1;
      if (!a.isCenter && b.isCenter) return 1;
      return a.diff - b.diff;
    });

    return matches;
  }, [chain, rangeSize, maxDiff]);

  const handleBuy = async (pair) => {
    setIsOrdering(true);
    try {
      // Mock API call or real API call to /orders
      const payloadCE = {
        symbol: `${symbol}_${pair.callStrike}_CE`,
        side: "BUY",
        qty: 1,
        price: pair.callLtp,
      };
      
      const payloadPE = {
        symbol: `${symbol}_${pair.putStrike}_PE`,
        side: "BUY",
        qty: 1,
        price: pair.putLtp,
      };

      await api.post("/orders", payloadCE);
      await api.post("/orders", payloadPE);

      toast.success(`Bought Strangle: ${pair.callStrike} CE & ${pair.putStrike} PE`);
      
      // Add to tracked pairs
      setTrackedPairs(prev => [
        {
          id: Date.now(),
          symbol,
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
    const callRow = chain?.rows?.find(r => r.strike === t.callStrike);
    const putRow = chain?.rows?.find(r => r.strike === t.putStrike);
    
    const currCall = callRow?.ce_ltp || t.buyCallLtp;
    const currPut = putRow?.pe_ltp || t.buyPutLtp;

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
    <div className="space-y-4">
      <Panel 
        title="Premium Comparison Matcher" 
        kicker="Delta-neutral combos"
        right={
          <div className="flex gap-4">
            <div className="flex items-center gap-2">
              <span className="dim text-xs">Range:</span>
              <select 
                className="terminal !w-auto !py-1 !text-xs"
                value={rangeSize}
                onChange={e => setRangeSize(Number(e.target.value))}
              >
                <option value={5}>± 5 Strikes</option>
                <option value={10}>± 10 Strikes</option>
                <option value={15}>± 15 Strikes</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <span className="dim text-xs">Max Diff:</span>
              <select 
                className="terminal !w-auto !py-1 !text-xs"
                value={maxDiff}
                onChange={e => setMaxDiff(Number(e.target.value))}
              >
                <option value={2}>≤ 2.0</option>
                <option value={5}>≤ 5.0</option>
                <option value={10}>≤ 10.0</option>
                <option value={20}>≤ 20.0</option>
                <option value={50}>≤ 50.0</option>
              </select>
            </div>
          </div>
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-[#333] text-xs dim">
                <th className="p-2 font-normal">CALL STRIKE</th>
                <th className="p-2 font-normal">CALL LTP</th>
                <th className="p-2 font-normal">PUT STRIKE</th>
                <th className="p-2 font-normal">PUT LTP</th>
                <th className="p-2 font-normal">DIFFERENCE</th>
                <th className="p-2 font-normal text-right">ACTION</th>
              </tr>
            </thead>
            <tbody>
              {pairs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-4 text-center dim text-sm">
                    No matching pairs found in this range.
                  </td>
                </tr>
              ) : (
                pairs.map((p, idx) => (
                  <tr key={idx} className={`border-b border-[#EBE3DB] ${p.isCenter ? "bg-[#EBE3DB]" : "bg-white hover:bg-[#F5F0EB]"}`}>
                    <td className="p-2 text-sm mono">
                      {fmtNum(p.callStrike, 0)} {p.isCenter && <span className="dim text-xs">(ATM)</span>}
                    </td>
                    <td className="p-2 text-sm mono buy">{fmtNum(p.callLtp)}</td>
                    <td className="p-2 text-sm mono">
                      {fmtNum(p.putStrike, 0)}
                    </td>
                    <td className="p-2 text-sm mono sell">{fmtNum(p.putLtp)}</td>
                    <td className="p-2 text-sm mono" style={{ color: p.diff < 2 ? "#0096FF" : "inherit" }}>
                      {fmtNum(p.diff)}
                    </td>
                    <td className="p-2 text-right">
                      <button 
                        onClick={() => handleBuy(p)}
                        disabled={isOrdering}
                        className="px-3 py-1 bg-[#D6C5B3] text-[#4A3F35] text-xs font-medium rounded border border-[#C2B09C] hover:bg-[#C2B09C] transition disabled:opacity-50"
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
                    <tr key={t.id} className="border-b border-gray-300 hover:bg-gray-100">
                      <td className="p-2 text-sm dim">{t.timestamp}</td>
                      <td className="p-2 text-sm mono">
                        {t.symbol} {fmtNum(t.callStrike, 0)}CE + {fmtNum(t.putStrike, 0)}PE
                      </td>
                      <td className={`p-2 text-sm mono ${pnl.callPnl >= 0 ? "buy" : "sell"}`}>
                        {pnl.callPnl >= 0 ? "+" : ""}{fmtNum(pnl.callPnl)}
                      </td>
                      <td className={`p-2 text-sm mono ${pnl.putPnl >= 0 ? "buy" : "sell"}`}>
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
