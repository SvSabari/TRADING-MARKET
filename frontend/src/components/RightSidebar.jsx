import { useState, useEffect } from "react";
import { Plus, X, ChartLine } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import "./RightSidebar.css";
import QuickOrderPanel from "./QuickOrderPanel";

export default function RightSidebar() {
  const [activeTab, setActiveTab] = useState("watchlist");
  const [watchlist, setWatchlist] = useState([]);
  const [watchlistInput, setWatchlistInput] = useState("");
  const [prices, setPrices] = useState({});

  // Load watchlist from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("watchlist");
    if (saved) {
      try {
        setWatchlist(JSON.parse(saved));
      } catch (e) {
        console.error("Failed to load watchlist:", e);
      }
    }
  }, []);

  // Save watchlist to localStorage
  useEffect(() => {
    localStorage.setItem("watchlist", JSON.stringify(watchlist));
  }, [watchlist]);

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
        <button
          className={`tab-button ${activeTab === "watchlist" ? "active" : ""}`}
          onClick={() => setActiveTab("watchlist")}
        >
          <ChartLine size={18} />
          <span>Watchlist</span>
        </button>
        <button
          className={`tab-button ${activeTab === "order" ? "active" : ""}`}
          onClick={() => setActiveTab("order")}
        >
          <Plus size={18} />
          <span>Order</span>
        </button>
      </div>

      <div className="sidebar-content">
        {activeTab === "watchlist" && (
          <div className="watchlist-panel">
            <div className="watchlist-input-group">
              <input
                type="text"
                placeholder="Add symbol (e.g., RELIANCE)"
                value={watchlistInput}
                onChange={(e) => setWatchlistInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addToWatchlist()}
                className="watchlist-input"
                list="available-symbols"
              />
              <datalist id="available-symbols">
                {Object.keys(prices).map((sym) => (
                  <option key={sym} value={sym} />
                ))}
              </datalist>
              <button onClick={addToWatchlist} className="add-button">
                <Plus size={16} />
              </button>
            </div>

            <div className="watchlist-items">
              {watchlist.length === 0 ? (
                <div className="empty-state">
                  <p>No symbols added</p>
                  <p className="text-xs">Add symbols to your watchlist</p>
                </div>
              ) : (
                watchlist.map((symbol) => {
                  const tick = prices[symbol];
                  return (
                    <div key={symbol} className="watchlist-item">
                      <div className="watchlist-symbol">
                        <div className="symbol-name">{symbol}</div>
                        {tick && (
                          <>
                            <div className="symbol-price">₹{tick.ltp.toFixed(2)}</div>
                            <div
                              className={`symbol-change ${
                                tick.change_pct >= 0 ? "positive" : "negative"
                              }`}
                            >
                              {tick.change_pct >= 0 ? "+" : ""}
                              {tick.change_pct.toFixed(2)}%
                            </div>
                          </>
                        )}
                      </div>
                      <button
                        onClick={() => removeFromWatchlist(symbol)}
                        className="remove-button"
                      >
                        <X size={16} />
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}

        {activeTab === "order" && <QuickOrderPanel watchlist={watchlist} />}
      </div>
    </div>
  );
}
