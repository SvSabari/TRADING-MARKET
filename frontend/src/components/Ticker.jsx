import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import "./Ticker.css";

export default function Ticker() {
  const [ticks, setTicks] = useState([]);
  const [repeatedTicks, setRepeatedTicks] = useState([]);

  useEffect(() => {
    const fetchSnapshot = async () => {
      try {
        const { data } = await api.get("/market/snapshot");
        setTicks(data.ticks || []);
      } catch (e) {
        console.error("Ticker snapshot failed:", e);
      }
    };

    fetchSnapshot();
    const interval = setInterval(fetchSnapshot, 5000);
    return () => clearInterval(interval);
  }, []);

  // Repeat ticks 3 times for seamless scroll
  useEffect(() => {
    setRepeatedTicks([...ticks, ...ticks, ...ticks]);
  }, [ticks]);

  if (!repeatedTicks.length) {
    return (
      <div className="ticker">
        <div className="ticker-content">
          <div className="ticker-placeholder">Loading market data...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="ticker">
      <div className="ticker-content">
        <div className="ticker-scroll">
          {repeatedTicks.map((tick, idx) => (
            <div key={idx} className="ticker-item">
              <span className="ticker-symbol">{tick.symbol}</span>
              <span className="ticker-price">₹{tick.ltp.toFixed(2)}</span>
              <span className={`ticker-change ${tick.change_pct >= 0 ? "buy" : "sell"}`}>
                {tick.change_pct >= 0 ? "▲" : "▼"}{Math.abs(tick.change_pct).toFixed(2)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
