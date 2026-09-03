import { useState, useEffect } from "react";
import { Plus, X, ChartLine } from "@phosphor-icons/react";
import { useLocation } from "react-router-dom";
import { api } from "@/lib/api";
import "./RightSidebar.css";
import QuickOrderPanel from "./QuickOrderPanel";
import MarketInsights from "./MarketInsights";

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
      </div>

      <div className="sidebar-content">
        {isDashboardOrChart && activeTab === "signals" && (
          <div className="flex-1 overflow-hidden h-full">
            <MarketInsights />
          </div>
        )}

        {activeTab === "order" && <QuickOrderPanel watchlist={watchlist} />}
      </div>
    </div>
  );
}
