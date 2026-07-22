import { useState, useEffect } from "react";
import { CheckCircle } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import "./QuickOrderPanel.css";

const INDICES = [
  { label: "NIFTY 50", value: "NIFTY" },
  { label: "BANK NIFTY", value: "BANKNIFTY" },
  { label: "FINNIFTY", value: "FINNIFTY" },
  { label: "MIDCP NIFTY", value: "MIDCPNIFTY" },
  { label: "NIFTY NEXT 50", value: "NIFTYNXT50" },
  { label: "SENSEX", value: "SENSEX" },
];

export default function QuickOrderPanel({ watchlist = [] }) {
  const [instrumentType, setInstrumentType] = useState("stock");
  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState("BUY");
  const [quantity, setQuantity] = useState(1);
  const [price, setPrice] = useState("");
  const [selectedIndex, setSelectedIndex] = useState("NIFTY");
  const [optionType, setOptionType] = useState("CE");
  const [strikePrice, setStrikePrice] = useState("");
  const [expiry, setExpiry] = useState("");
  const [optionChain, setOptionChain] = useState([]);
  const [loading, setLoading] = useState(false);
  const [prices, setPrices] = useState({});

  // Fetch prices for dropdown population
  useEffect(() => {
    const fetchPrices = async () => {
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
  }, []);

  // Auto-populate price when symbol changes
  useEffect(() => {
    if (prices[symbol]) {
      setPrice(prices[symbol].ltp.toFixed(2));
    }
  }, [symbol, prices]);

  const placedOrder = async () => {
    if (!quantity || !price) {
      toast.error("Please fill quantity and price");
      return;
    }
    if (instrumentType === "stock" && !symbol) {
      toast.error("Please select a symbol");
      return;
    }
    if (instrumentType === "option" && (!selectedIndex || !strikePrice)) {
      toast.error("Please fill index and strike price");
      return;
    }

    setLoading(true);
    try {
      const payload = {
        side,
        qty: parseInt(quantity),
        price: parseFloat(price),
      };

      if (instrumentType === "stock") {
        payload.symbol = symbol;
      } else if (instrumentType === "futures") {
        payload.symbol = expiry ? `${selectedIndex}_${expiry}_FUT` : `${selectedIndex}_FUT`;
      } else if (instrumentType === "option") {
        payload.symbol = expiry ? `${selectedIndex}_${expiry}_${strikePrice}_${optionType}` : `${selectedIndex}_${strikePrice}_${optionType}`;
      }

      await api.post("/orders", payload);
      toast.success("Order placed successfully!");

      // Reset form
      setSymbol("");
      setQuantity(1);
      setPrice("");
    } catch (e) {
      console.error("Order failed:", e);
      if (e.response?.data?.detail === "NO_EXECUTION_BROKER") {
        if (window.confirm("The Execution broker is not connected. Would you like to place this order in Mock (Paper Trading) mode instead?")) {
          try {
            const payload = {
              side,
              qty: parseInt(quantity),
              price: parseFloat(price),
              force_mock: true,
            };
            if (instrumentType === "stock") {
              payload.symbol = symbol;
            } else if (instrumentType === "futures") {
              payload.symbol = expiry ? `${selectedIndex}_${expiry}_FUT` : `${selectedIndex}_FUT`;
            } else if (instrumentType === "option") {
              payload.symbol = expiry ? `${selectedIndex}_${expiry}_${strikePrice}_${optionType}` : `${selectedIndex}_${strikePrice}_${optionType}`;
            }
            await api.post("/orders", payload);
            toast.success("Mock Order placed successfully!");
            setSymbol("");
            setQuantity(1);
            setPrice("");
          } catch (mockError) {
            toast.error(mockError.response?.data?.detail || "Mock order failed");
          }
        }
      } else {
        toast.error(e.response?.data?.detail || "Order placement failed");
      }
    } finally {
      setLoading(false);
    }
  };

  const renderStockForm = () => (
    <div className="order-form-group">
      <label>Symbol *</label>
      <select
        value={symbol}
        onChange={(e) => setSymbol(e.target.value)}
        className="order-input"
      >
        <option value="">Select Symbol</option>
        {Object.keys(prices).map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>

      <label>Side *</label>
      <div className="side-buttons">
        <button
          className={`side-btn buy ${side === "BUY" ? "active" : ""}`}
          onClick={() => setSide("BUY")}
        >
          BUY
        </button>
        <button
          className={`side-btn sell ${side === "SELL" ? "active" : ""}`}
          onClick={() => setSide("SELL")}
        >
          SELL
        </button>
      </div>

      <label>Quantity *</label>
      <input
        type="number"
        min="1"
        value={quantity}
        onChange={(e) => setQuantity(e.target.value)}
        className="order-input"
      />

      <label>Price *</label>
      <input
        type="number"
        step="0.01"
        value={price}
        onChange={(e) => setPrice(e.target.value)}
        className="order-input"
      />
    </div>
  );

  const renderFuturesForm = () => (
    <div className="order-form-group">
      <label>Instrument *</label>
      <div className="index-buttons">
        {INDICES.map((idx) => (
          <button
            key={idx.value}
            className={`index-btn ${selectedIndex === idx.value ? "active" : ""}`}
            onClick={() => setSelectedIndex(idx.value)}
          >
            {idx.label}
          </button>
        ))}
      </div>

      <label>Side *</label>
      <div className="side-buttons">
        <button
          className={`side-btn buy ${side === "BUY" ? "active" : ""}`}
          onClick={() => setSide("BUY")}
        >
          BUY
        </button>
        <button
          className={`side-btn sell ${side === "SELL" ? "active" : ""}`}
          onClick={() => setSide("SELL")}
        >
          SELL
        </button>
      </div>

      <label>Expiry (Optional)</label>
      <input
        type="text"
        value={expiry}
        onChange={(e) => setExpiry(e.target.value.toUpperCase())}
        className="order-input"
        placeholder="e.g., 25JUL"
      />

      <label>Quantity *</label>
      <input
        type="number"
        min="1"
        value={quantity}
        onChange={(e) => setQuantity(e.target.value)}
        className="order-input"
      />

      <label>Price *</label>
      <input
        type="number"
        step="0.01"
        value={price}
        onChange={(e) => setPrice(e.target.value)}
        className="order-input"
        placeholder="e.g., 20000.00"
      />
    </div>
  );

  const renderOptionsForm = () => (
    <div className="order-form-group">
      <label>Index *</label>
      <div className="index-buttons">
        {INDICES.map((idx) => (
          <button
            key={idx.value}
            className={`index-btn ${selectedIndex === idx.value ? "active" : ""}`}
            onClick={() => setSelectedIndex(idx.value)}
          >
            {idx.label}
          </button>
        ))}
      </div>

      <label>Option Type *</label>
      <div className="side-buttons">
        <button
          className={`side-btn buy ${optionType === "CE" ? "active" : ""}`}
          onClick={() => setOptionType("CE")}
        >
          CALL
        </button>
        <button
          className={`side-btn sell ${optionType === "PE" ? "active" : ""}`}
          onClick={() => setOptionType("PE")}
        >
          PUT
        </button>
      </div>

      <label>Strike Price *</label>
      <input
        type="number"
        step="100"
        value={strikePrice}
        onChange={(e) => setStrikePrice(e.target.value)}
        className="order-input"
        placeholder="e.g., 20000"
      />

      <label>Side *</label>
      <div className="side-buttons">
        <button
          className={`side-btn buy ${side === "BUY" ? "active" : ""}`}
          onClick={() => setSide("BUY")}
        >
          BUY
        </button>
        <button
          className={`side-btn sell ${side === "SELL" ? "active" : ""}`}
          onClick={() => setSide("SELL")}
        >
          SELL
        </button>
      </div>

      <label>Expiry (Optional)</label>
      <input
        type="text"
        value={expiry}
        onChange={(e) => setExpiry(e.target.value.toUpperCase())}
        className="order-input"
        placeholder="e.g., 25JUL"
      />

      <label>Quantity *</label>
      <input
        type="number"
        min="1"
        value={quantity}
        onChange={(e) => setQuantity(e.target.value)}
        className="order-input"
      />

      <label>Price *</label>
      <input
        type="number"
        step="0.01"
        value={price}
        onChange={(e) => setPrice(e.target.value)}
        className="order-input"
      />
    </div>
  );

  return (
    <div className="quick-order-panel">
      <div className="order-type-tabs">
        <button
          className={`order-type-btn ${instrumentType === "stock" ? "active" : ""}`}
          onClick={() => setInstrumentType("stock")}
        >
          Stocks
        </button>
        <button
          className={`order-type-btn ${instrumentType === "futures" ? "active" : ""}`}
          onClick={() => setInstrumentType("futures")}
        >
          Futures
        </button>
        <button
          className={`order-type-btn ${instrumentType === "option" ? "active" : ""}`}
          onClick={() => setInstrumentType("option")}
        >
          Options
        </button>
      </div>

      <div className="order-form">
        {instrumentType === "stock" && renderStockForm()}
        {instrumentType === "futures" && renderFuturesForm()}
        {instrumentType === "option" && renderOptionsForm()}

        <button
          onClick={placedOrder}
          disabled={loading}
          className="place-order-btn"
        >
          <CheckCircle size={16} />
          <span>{loading ? "Placing..." : "Place Order"}</span>
        </button>
      </div>
    </div>
  );
}
