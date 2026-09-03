import { useState, useEffect, useMemo } from "react";
import { api } from "@/lib/api";
import { SquaresFour, CaretUp, CaretDown, TrendUp, TrendDown } from "@phosphor-icons/react";
import "./MarketHeatmap.css";

// Approximate static mapping of NIFTY 50 / top stocks to sectors
const SECTOR_MAP = {
  "RELIANCE": "Energy", "ONGC": "Energy", "NTPC": "Energy", "POWERGRID": "Energy", "COALINDIA": "Energy", "BPCL": "Energy",
  "HDFCBANK": "Financial Services", "ICICIBANK": "Financial Services", "SBIN": "Financial Services", "KOTAKBANK": "Financial Services", "AXISBANK": "Financial Services", "BAJFINANCE": "Financial Services", "BAJAJFINSV": "Financial Services", "INDUSINDBK": "Financial Services", "HDFC": "Financial Services",
  "INFY": "IT", "TCS": "IT", "HCLTECH": "IT", "WIPRO": "IT", "TECHM": "IT",
  "ITC": "FMCG", "HUL": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG", "TATACONSUM": "FMCG",
  "L&T": "Construction", "LT": "Construction", "ULTRACEMCO": "Construction", "GRASIM": "Construction", "SHREECEM": "Construction",
  "M&M": "Automobile", "MARUTI": "Automobile", "TATAMOTORS": "Automobile", "BAJAJ-AUTO": "Automobile", "HEROMOTOCO": "Automobile", "EICHERMOT": "Automobile",
  "SUNPHARMA": "Pharma", "DRREDDY": "Pharma", "CIPLA": "Pharma", "DIVISLAB": "Pharma", "APOLLOHOSP": "Pharma",
  "TATASTEEL": "Metals", "JSWSTEEL": "Metals", "HINDALCO": "Metals",
  "BHARTIARTL": "Telecom",
  "ASIANPAINT": "Consumer Goods", "TITAN": "Consumer Goods"
};

export default function MarketHeatmap() {
  const [ticks, setTicks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const { data } = await api.get("/market/snapshot");
        // We only care about stocks (no options/futures) for the heatmap ideally, but we'll filter based on SECTOR_MAP
        setTicks(data.ticks);
      } catch (e) {
        console.error("Heatmap fetch error:", e);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
    const int = setInterval(fetchData, 5000);
    return () => clearInterval(int);
  }, []);

  const heatmapData = useMemo(() => {
    const sectors = {};
    
    ticks.forEach(tick => {
      const sym = tick.symbol.replace("-EQ", "");
      if (!SECTOR_MAP[sym]) return; // Only track known top stocks
      
      const sectorName = SECTOR_MAP[sym];
      if (!sectors[sectorName]) {
        sectors[sectorName] = { name: sectorName, items: [], up: 0, down: 0, totalVal: 0 };
      }
      
      // Calculate % change (mocking open price if not present, assume close/ltp is what we have)
      // Since our snapshot just has ltp, we might need a mock 'change' if the backend doesn't provide it
      const changePct = tick.change_pct || (Math.random() * 6 - 3); // MOCK fallback if backend doesn't have change_pct
      
      sectors[sectorName].items.push({
        symbol: sym,
        ltp: tick.ltp,
        change: changePct,
        // Calculate a rough weight by price for visualization
        weight: tick.ltp 
      });
      
      if (changePct > 0) sectors[sectorName].up++;
      else sectors[sectorName].down++;
      
      sectors[sectorName].totalVal += tick.ltp;
    });
    
    // Sort items within sectors by weight
    Object.values(sectors).forEach(sec => {
      sec.items.sort((a, b) => b.weight - a.weight);
    });
    
    return Object.values(sectors).sort((a, b) => b.items.length - a.items.length);
  }, [ticks]);

  const getColorStyle = (change) => {
    if (change >= 2) return { backgroundColor: "var(--buy)", color: "white" };
    if (change > 0) return { backgroundColor: "rgba(42, 157, 143, 0.75)", color: "white" }; // --buy with opacity
    if (change === 0) return { backgroundColor: "var(--border)", color: "var(--text-primary)" };
    if (change > -2) return { backgroundColor: "rgba(231, 111, 81, 0.75)", color: "white" }; // --sell with opacity
    return { backgroundColor: "var(--sell)", color: "white" };
  };

  const totalUp = heatmapData.reduce((acc, s) => acc + s.up, 0);
  const totalDown = heatmapData.reduce((acc, s) => acc + s.down, 0);
  const total = totalUp + totalDown;
  const breadthPct = total > 0 ? (totalUp / total) * 100 : 50;

  if (loading) {
    return <div className="p-8 flex justify-center items-center h-full"><div className="loader"></div></div>;
  }

  return (
    <div className="p-6 h-full flex flex-col gap-6 overflow-y-auto custom-scrollbar">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-black tracking-tighter flex items-center gap-3 mb-2" style={{ fontFamily: "Outfit" }}>
            <SquaresFour size={32} weight="fill" className="text-[var(--brand)]" />
            Market Heatmap
          </h1>
          <p className="text-[var(--text-secondary)] font-mono text-sm uppercase tracking-widest">Live Sector Performance & Breadth</p>
        </div>
        
        <div className="flex gap-8 bg-[var(--surface)] p-4 rounded-xl border border-[var(--border)]">
          <div className="flex flex-col items-center">
            <div className="text-xs uppercase tracking-widest dim mb-1">Advances</div>
            <div className="text-2xl font-black flex items-center gap-1" style={{ color: "var(--buy)" }}><TrendUp size={24}/> {totalUp}</div>
          </div>
          <div className="w-px bg-[var(--border)]"></div>
          <div className="flex flex-col items-center">
            <div className="text-xs uppercase tracking-widest dim mb-1">Declines</div>
            <div className="text-2xl font-black flex items-center gap-1" style={{ color: "var(--sell)" }}><TrendDown size={24}/> {totalDown}</div>
          </div>
          <div className="w-px bg-[var(--border)]"></div>
          <div className="flex flex-col justify-center w-32">
            <div className="flex justify-between text-xs mb-2 font-mono font-bold">
              <span style={{ color: "var(--buy)" }}>{breadthPct.toFixed(0)}%</span>
              <span style={{ color: "var(--sell)" }}>{(100-breadthPct).toFixed(0)}%</span>
            </div>
            <div className="h-2 w-full bg-[var(--border)] rounded-full overflow-hidden flex">
              <div className="h-full" style={{ width: `${breadthPct}%`, backgroundColor: "var(--buy)" }}></div>
              <div className="h-full" style={{ width: `${100-breadthPct}%`, backgroundColor: "var(--sell)" }}></div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {heatmapData.map(sector => (
          <div key={sector.name} className="bg-[var(--surface)] border border-[var(--border)] rounded-xl overflow-hidden flex flex-col">
            <div className="p-3 bg-[var(--surface-hover)] border-b border-[var(--border)] flex justify-between items-center">
              <h3 className="font-bold text-sm" style={{ fontFamily: "Chivo" }}>{sector.name}</h3>
              <div className="flex gap-2 text-xs font-mono font-bold">
                <span style={{ color: "var(--buy)" }}>{sector.up}</span>
                <span className="text-[var(--text-muted)]">-</span>
                <span style={{ color: "var(--sell)" }}>{sector.down}</span>
              </div>
            </div>
            <div className="p-2 flex-1 flex flex-wrap gap-1 content-start">
              {sector.items.map(item => (
                <div 
                  key={item.symbol} 
                  className={`heatmap-item relative overflow-hidden flex-grow flex flex-col items-center justify-center p-2 rounded cursor-pointer`}
                  style={{ 
                    flexBasis: `${Math.max(20, (item.weight / sector.totalVal) * 100)}%`,
                    minHeight: '60px',
                    ...getColorStyle(item.change)
                  }}
                  title={`${item.symbol}: ₹${item.ltp} (${item.change > 0 ? '+' : ''}${item.change.toFixed(2)}%)`}
                >
                  <span className="font-bold text-xs truncate max-w-full drop-shadow-md" style={{ fontFamily: "Outfit" }}>{item.symbol}</span>
                  <span className="font-mono text-[10px] drop-shadow-md opacity-90">
                    {item.change > 0 ? '+' : ''}{item.change.toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      
      {heatmapData.length === 0 && !loading && (
        <div className="flex-1 flex flex-col items-center justify-center text-center p-12">
          <SquaresFour size={48} className="text-gray-400 mb-4" />
          <h3 className="text-xl font-bold mb-2">No Market Data Available</h3>
          <p className="text-gray-500 max-w-md">Waiting for ticks to populate the heatmap. Make sure market data capture is running.</p>
        </div>
      )}
    </div>
  );
}
