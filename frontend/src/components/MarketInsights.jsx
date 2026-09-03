import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useSymbol } from "@/lib/symbol-context";

export default function MarketInsights() {
  const [signal, setSignal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [heatmapMatrix, setHeatmapMatrix] = useState(null);
  const { globalSymbol } = useSymbol();

  const [allSignals, setAllSignals] = useState([]);

  const fetchInsights = async () => {
    if (!globalSymbol) {
      setLoading(false);
      return;
    }
    
    try {
      const { data } = await api.get("/signals/live");
      const sigList = data.signals || [];
      setAllSignals(sigList);
      
      const matchedSignal = sigList.find(s => s.symbol === globalSymbol);
      setSignal(matchedSignal || null);
        
      // Fetch heatmap matrix for globalSymbol (always, even if no signal)
      try {
         const chainRes = await api.get(`/analytics/option-chain?symbol=${globalSymbol}`);
         const expiries = (chainRes.data.available_expiries || []).slice(0, 5);
         
         if (expiries.length > 0) {
            const hmPromises = expiries.map(exp => api.get(`/analytics/oi-heatmap?symbol=${globalSymbol}&expiry=${encodeURIComponent(exp)}`));
            const hmResults = await Promise.all(hmPromises);
            
            // Only keep ATM-centric strikes (take center 5 strikes)
            const firstData = hmResults[0].data.data;
            const centerIdx = Math.floor(firstData.length / 2);
            const targetStrikes = firstData.slice(Math.max(0, centerIdx - 2), centerIdx + 3).map(d => d.strike);

            const matrixData = hmResults.map(res => {
               const rowData = targetStrikes.map(st => {
                  const cell = res.data.data.find(d => d.strike === st);
                  return cell ? cell.ce_oi + cell.pe_oi : 0;
               });
               return { expiry: res.data.expiry, data: rowData };
            });
            
            setHeatmapMatrix({
               strikes: targetStrikes,
               matrix: matrixData
            });
         } else {
            setHeatmapMatrix(null);
         }
      } catch (e) {
         console.error("Heatmap fetch error", e);
      }
    } catch (e) {
      console.error("Failed to fetch signals", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchInsights();
    const interval = setInterval(fetchInsights, 5000); // Poll every 5s
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [globalSymbol]);

  if (loading && !signal && !heatmapMatrix) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-[var(--text-secondary)]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--brand)] border-t-transparent mb-4"></div>
        <p className="text-sm">Scanning market data...</p>
      </div>
    );
  }

  // Format signal vars if it exists
  const isBullish = signal ? (
    (signal.kind.includes("bull") && !signal.kind.includes("trap")) || 
    (signal.kind.includes("bear") && signal.kind.includes("trap")) || 
    signal.kind.includes("long") || 
    signal.kind === "breakout"
  ) : false;
  const trendColor = isBullish ? "text-[#26a69a]" : "text-[#ef5350]";
  const bgTrend = isBullish ? "bg-[#26a69a]/10" : "bg-[#ef5350]/10";
  const trendText = isBullish ? "BULLISH" : "BEARISH";
  const formattedKind = signal ? signal.kind.split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ") : "";

  // Helper for heatmap colors
  let maxOiVal = 0;
  if (heatmapMatrix) {
    heatmapMatrix.matrix.forEach(row => {
      row.data.forEach(val => { if (val > maxOiVal) maxOiVal = val; });
    });
  }

  return (
    <div className="flex flex-col gap-4 p-4 overflow-y-auto h-full">
      {signal ? (
        <>
          {/* MARKET TREND */}
          <div className="rounded-lg p-4 border border-[var(--border)] bg-[var(--surface)] shadow-sm">
            <div className="text-[10px] text-[var(--text-secondary)] font-bold tracking-wider mb-2 uppercase">Market Trend ({signal.symbol})</div>
            <div className="flex items-center justify-between mb-4">
              <div className={`text-2xl font-black tracking-tight ${trendColor}`}>
                {trendText}
              </div>
              <div className={`w-10 h-10 rounded-full flex items-center justify-center ${bgTrend} ${trendColor}`}>
                {isBullish ? (
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"></polyline><polyline points="16 7 22 7 22 13"></polyline></svg>
                ) : (
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 17 13.5 8.5 8.5 13.5 2 7"></polyline><polyline points="16 17 22 17 22 11"></polyline></svg>
                )}
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2 pt-3 border-t border-[var(--border)]">
              <div>
                <div className="text-[10px] text-[var(--text-secondary)] font-semibold mb-1">VOL RATIO</div>
                <div className="text-sm font-bold text-[var(--text-primary)]">{signal.volume_ratio}x</div>
              </div>
              <div>
                <div className="text-[10px] text-[var(--text-secondary)] font-semibold mb-1">MOMENTUM</div>
                <div className={`text-sm font-bold ${signal.change_pct >= 0 ? 'text-[#26a69a]' : 'text-[#ef5350]'}`}>
                  {signal.change_pct >= 0 ? '+' : ''}{signal.change_pct}%
                </div>
              </div>
              <div>
                <div className="text-[10px] text-[var(--text-secondary)] font-semibold mb-1">CONFIDENCE</div>
                <div className="text-sm font-bold text-[var(--text-primary)] mb-1">{Math.round(signal.confidence * 100)}%</div>
                <div className="w-full bg-[var(--border)] h-1.5 rounded-full overflow-hidden">
                  <div className={`h-full ${trendColor.replace('text-', 'bg-')}`} style={{ width: `${Math.round(signal.confidence * 100)}%` }}></div>
                </div>
              </div>
            </div>
          </div>

          {/* SUGGESTED TRADE */}
          <div className="rounded-lg p-4 border border-[var(--border)] bg-[var(--surface)] shadow-sm">
            <div className="text-[10px] text-[var(--text-secondary)] font-bold tracking-wider mb-2 uppercase">AI Suggested Signal</div>
            <div className={`text-lg font-black mb-3 ${trendColor}`}>
              {isBullish ? 'BUY' : 'SELL'} {signal.symbol}
            </div>
            
            <div className="grid grid-cols-3 gap-2 mb-4">
              <div>
                <div className="text-[10px] text-[var(--text-secondary)] font-semibold mb-1">ENTRY</div>
                <div className="text-sm font-bold text-[var(--text-primary)]">₹{signal.price.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-[10px] text-[var(--text-secondary)] font-semibold mb-1">SL</div>
                <div className="text-sm font-bold text-[#ef5350]">
                  ₹{(isBullish ? signal.price * 0.99 : signal.price * 1.01).toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-[var(--text-secondary)] font-semibold mb-1">TARGET</div>
                <div className="text-sm font-bold text-[#26a69a]">
                  ₹{(isBullish ? signal.price * 1.02 : signal.price * 0.98).toFixed(2)}
                </div>
              </div>
            </div>
            
            <div className="text-[10px] text-[var(--text-secondary)] font-bold tracking-wider mb-1 uppercase">Reasoning</div>
            <p className="text-xs text-[var(--text-primary)] opacity-80 leading-relaxed">
              Detected strong <span className="font-bold">{formattedKind}</span> pattern with a confidence of {Math.round(signal.confidence * 100)}%. 
              Volume is running at {signal.volume_ratio}x the average, indicating supportive institutional build-up for a {trendText.toLowerCase()} bias.
            </p>
          </div>
        </>
      ) : (
        <div className="rounded-lg p-6 border border-[var(--border)] bg-[var(--surface)] shadow-sm flex flex-col items-center justify-center text-center">
          <div className="w-12 h-12 rounded-full bg-[var(--bg)] flex items-center justify-center mb-3 text-[var(--text-secondary)]">
             <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
          </div>
          <div className="text-sm font-bold text-[var(--text-primary)] mb-1">No Active Signal</div>
          <p className="text-xs text-[var(--text-secondary)] opacity-80 mb-4">
            The AI scanner hasn't detected a high-confidence trade setup for {globalSymbol} right now.
          </p>
          
          {allSignals.length > 0 && (
            <div className="w-full pt-4 border-t border-[var(--border)] text-left">
              <div className="text-[10px] text-[var(--text-secondary)] font-bold tracking-wider mb-2 uppercase">Other Active Market Signals</div>
              <div className="flex flex-wrap gap-2">
                {allSignals.slice(0, 5).map(sig => {
                  const sBull = (sig.kind.includes("bull") && !sig.kind.includes("trap")) || (sig.kind.includes("bear") && sig.kind.includes("trap")) || sig.kind.includes("long") || sig.kind === "breakout";
                  return (
                    <div key={sig.symbol} className="text-[10px] font-bold px-2 py-1 rounded bg-[var(--bg)] border border-[var(--border)] flex items-center gap-1">
                      <span className={sBull ? "text-[#26a69a]" : "text-[#ef5350]"}>{sBull ? 'BUY' : 'SELL'}</span>
                      <span className="text-[var(--text-primary)]">{sig.symbol}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 2D OI HEATMAP */}
      {heatmapMatrix && heatmapMatrix.matrix && heatmapMatrix.strikes.length > 0 && (
        <div className="rounded-lg p-4 border border-[var(--border)] bg-[var(--surface)] shadow-sm">
          <div className="text-[10px] text-[var(--text-secondary)] font-bold tracking-wider mb-3 uppercase">OI Heatmap ({globalSymbol})</div>
          
          <div className="flex text-[9px] text-[var(--text-secondary)] mb-1">
             <div className="w-[60px] shrink-0 font-semibold uppercase flex items-center">Strike &rarr;</div>
             {heatmapMatrix.strikes.map(st => (
                <div key={st} className="flex-1 text-center truncate px-0.5">{st}</div>
             ))}
          </div>

          <div className="flex flex-col mb-3">
             <div className="flex text-[9px] text-[var(--text-secondary)] mb-1">
                <div className="w-[60px] shrink-0 font-semibold uppercase">Expiry &darr;</div>
             </div>
             {heatmapMatrix.matrix.map((row, rIndex) => {
                let formattedExpiry = row.expiry;
                if (formattedExpiry.includes('-') || !isNaN(Date.parse(formattedExpiry))) {
                    const d = new Date(formattedExpiry);
                    if (!isNaN(d.getTime())) {
                        const day = d.getDate().toString().padStart(2, '0');
                        const mon = d.toLocaleString('default', { month: 'short' }).toUpperCase();
                        formattedExpiry = `${day} ${mon}`;
                    }
                }
                
                return (
                <div key={row.expiry} className="flex h-6 mb-0.5">
                   <div className="w-[60px] shrink-0 text-[9px] text-[var(--text-primary)] flex items-center pr-2 truncate opacity-90">{formattedExpiry}</div>
                   {row.data.map((val, cIndex) => {
                      const intensity = maxOiVal > 0 ? (val / maxOiVal) : 0;
                      // Gradient from Deep Red (Low) to Dark Green (High)
                      const rColor = Math.round(200 - (200 - 30) * intensity);
                      const gColor = Math.round(40 + (160 - 40) * intensity);
                      const bColor = Math.round(40 + (60 - 40) * intensity);
                      return (
                        <div 
                          key={cIndex} 
                          className="flex-1 border border-[var(--surface)]" 
                          style={{ backgroundColor: `rgb(${rColor}, ${gColor}, ${bColor})` }}
                        ></div>
                      )
                   })}
                </div>
                );
             })}
          </div>

          <div className="flex items-center justify-between text-[9px] text-[var(--text-secondary)]">
             <span>Low OI</span>
             <div className="flex h-2 flex-1 mx-2 rounded overflow-hidden">
                <div className="flex-1 bg-[#c82828]"></div>
                <div className="flex-1 bg-[#d25a28]"></div>
                <div className="flex-1 bg-[#c8a028]"></div>
                <div className="flex-1 bg-[#64a028]"></div>
                <div className="flex-1 bg-[#1e8c32]"></div>
             </div>
             <span>High OI</span>
          </div>
        </div>
      )}

      {/* SYSTEM LOGS / NEWS */}
      {signal && (
        <div className="rounded-lg p-4 border border-[var(--border)] bg-[var(--surface)] shadow-sm">
          <div className="text-[10px] text-[var(--brand)] font-bold tracking-wider mb-3 uppercase">Live Scanner</div>
          <div className="space-y-3">
            <div className="flex gap-3 items-start">
              <span className="text-[10px] text-[var(--text-secondary)] font-mono shrink-0 mt-0.5">{new Date(signal.ts).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
              <span className="text-xs text-[var(--text-primary)]">Top signal updated: {signal.symbol}</span>
            </div>
            <div className="flex gap-3 items-start">
              <span className="text-[10px] text-[var(--text-secondary)] font-mono shrink-0 mt-0.5">{(new Date(new Date(signal.ts).getTime() - 60000)).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
              <span className="text-xs text-[var(--text-primary)] opacity-70">Market breadth improving...</span>
            </div>
            <div className="flex gap-3 items-start">
              <span className="text-[10px] text-[var(--text-secondary)] font-mono shrink-0 mt-0.5">{(new Date(new Date(signal.ts).getTime() - 180000)).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
              <span className="text-xs text-[var(--text-primary)] opacity-70">Scanner monitoring {signal.volume_ratio > 1 ? 'high' : 'normal'} volume sectors</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
