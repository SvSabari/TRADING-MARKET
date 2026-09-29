import { useState, useEffect } from "react";
import { Plus, X, ChartLine, Briefcase } from "@phosphor-icons/react";
import { useLocation } from "react-router-dom";
import { api } from "@/lib/api";
import "./RightSidebar.css";
import QuickOrderPanel from "./QuickOrderPanel";
import MarketInsights from "./MarketInsights";

function MiniPositions() {
  const [pos, setPos] = useState([]);
  useEffect(() => {
    let cancel = false;
    const load = async () => {
      try {
        const { data } = await api.get("/orders/positions");
        if (!cancel) setPos(data.positions);
      } catch (e) { console.error("api fetch failed:", e); }
    };
    load();
    const i = setInterval(load, 5000);
    return () => { cancel = true; clearInterval(i); };
  }, []);

  return (
    <div className="flex-1 overflow-auto h-full p-2">
      <h3 className="text-xs font-bold uppercase tracking-widest text-[var(--text-secondary)] mb-2 px-2">Open Positions</h3>
      <div className="space-y-2">
        {pos.length === 0 ? (
          <div className="text-xs text-[var(--text-secondary)] px-2 text-center mt-4">No open positions.</div>
        ) : (
          pos.map((p) => (
            <div key={p.id} className="bg-[var(--surface)] p-2 rounded border border-[var(--border)] text-xs flex justify-between items-center">
              <div>
                <div className="font-bold">{p.symbol}</div>
                <div className={`text-[10px] uppercase font-bold ${p.qty > 0 ? "text-green-500" : "text-red-500"}`}>
                  {p.qty > 0 ? "LONG" : "SHORT"} A {Math.abs(p.qty)}
                </div>
              </div>
              <div className="text-right">
                <div className={`font-mono font-bold ${p.pnl >= 0 ? "text-green-500" : "text-red-500"}`}>
                  {p.pnl >= 0 ? "+" : ""}{p.pnl.toFixed(2)}
                </div>
                <div className="text-[10px] text-[var(--text-secondary)]">Avg {p.avg_price.toFixed(2)}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function RightSidebar() {
  const location = useLocation();
  const isDashboardOrChart = location.pathname === "/" || location.pathname === "/dashboard" || location.pathname.startsWith("/chart");
  
  const [activeTab, setActiveTab] = useState(isDashboardOrChart ? "signals" : "order");

  // Ensure active tab switches to order if we navigate away from signals-supported pages
  useEffect(() => {
    if (!isDashboardOrChart && activeTab === "signals") {
      setActiveTab("order");
    }
  }, [isDashboardOrChart, activeTab]);
  useEffect(() => {
    const handleOpenOrder = () => setActiveTab("order");
    window.addEventListener("open-order-panel", handleOpenOrder);
    return () => window.removeEventListener("open-order-panel", handleOpenOrder);
  }, []);
  const [watchlist, setWatchlist] = useState(["RELIANCE"]); // Keep for quick order panel compatibility
  const [prices, setPrices] = useState({});
  const [watchlistInput, setWatchlistInput] = useState("");

  // Fetch prices for watchlist items
  useEffect(() => {
    const fetchPrices = async () => {
      if (!watchlist.length) return;
      
      try {
        const { data } = await api.get("/market/snapshot");
        const priceMap = {};
        data.ticks.forEach((tick) => {
          priceMap[tick.symbol] = tick;
        });
        setPrices(priceMap);
      } catch (e) {
        console.error("Failed to fetch prices:", e);
      }
    };

    fetchPrices();
    const interval = setInterval(fetchPrices, 5000);
    return () => clearInterval(interval);
  }, [watchlist]);

  const addToWatchlist = () => {
    const symbol = watchlistInput.toUpperCase().trim();
    if (symbol && !watchlist.includes(symbol)) {
      setWatchlist([...watchlist, symbol]);
      setWatchlistInput("");
    }
  };

  const removeFromWatchlist = (symbol) => {
    setWatchlist(watchlist.filter((s) => s !== symbol));
  };

  return (
    <div className="right-sidebar">
      <div className="sidebar-tabs">
        {isDashboardOrChart && (
          <button
            className={`tab-button ${activeTab === "signals" ? "active" : ""}`}
            onClick={() => setActiveTab("signals")}
          >
            <ChartLine size={18} />
            <span>Signals</span>
          </button>
        )}
        <button
          className={`tab-button ${activeTab === "order" ? "active" : ""}`}
          onClick={() => setActiveTab("order")}
        >
          <Plus size={18} />
          <span>Order</span>
        </button>
        <button
          className={`tab-button ${activeTab === "positions" ? "active" : ""}`}
          onClick={() => setActiveTab("positions")}
        >
          <Briefcase size={18} />
          <span>Positions</span>
        </button>
      </div>

      <div className="sidebar-content">
        {isDashboardOrChart && activeTab === "signals" && (
          <div className="flex-1 overflow-hidden h-full">
            <MarketInsights />
          </div>
        )}

        {activeTab === "order" && <QuickOrderPanel watchlist={watchlist} />}
        {activeTab === "positions" && <MiniPositions />}
      </div>
    </div>
  );
}
