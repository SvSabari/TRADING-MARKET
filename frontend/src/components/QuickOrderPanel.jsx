import { useState, useEffect, useRef } from "react";
import { CheckCircle, ArrowCounterClockwise, Lightning } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import LightningScalper from "./LightningScalper";
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
  const [copyToUsers, setCopyToUsers] = useState(true);
  const [strikePrice, setStrikePrice] = useState("");
  const [expiry, setExpiry] = useState("");
  const [isBracket, setIsBracket] = useState(false);
  const [target, setTarget] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [optionChain, setOptionChain] = useState([]);
  const [loading, setLoading] = useState(false);
  const [checkingMargin, setCheckingMargin] = useState(false);
  const [marginDetails, setMarginDetails] = useState(null);
  const [prices, setPrices] = useState({});
  const [isLightningMode, setIsLightningMode] = useState(false);

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

  const lastPopulatedSymbol = useRef("");

  // Auto-populate price when symbol changes
  useEffect(() => {
    if (symbol && prices[symbol] && lastPopulatedSymbol.current !== symbol) {
      setPrice(prices[symbol].ltp.toFixed(2));
      lastPopulatedSymbol.current = symbol;
    } else if (!symbol) {
      lastPopulatedSymbol.current = "";
    }
  }, [symbol, prices]);

  const _buildSymbol = () => {
    if (instrumentType === "stock") {
      return symbol;
    } else if (instrumentType === "futures") {
      return expiry ? `${selectedIndex}_${expiry}_FUT` : `${selectedIndex}_FUT`;
    } else if (instrumentType === "option") {
      return expiry ? `${selectedIndex}_${expiry}_${strikePrice}_${optionType}` : `${selectedIndex}_${strikePrice}_${optionType}`;
    }
    return symbol;
  };

  const checkMargin = async () => {
    if (!price || !quantity || !symbol) {
      toast.error("Please fill symbol, quantity and price");
      return;
    }
    
    // Construct symbol properly based on instrument type
    let finalSymbol = symbol;
    if (instrumentType === "futures") {
      finalSymbol = `${symbol}${expiry}FUT`;
    } else if (instrumentType === "option") {
      finalSymbol = `${symbol}${expiry}${strikePrice}${optionType}`;
    }

    setCheckingMargin(true);
    setMarginDetails(null);
    try {
      const isStock = instrumentType === "stock";
      const payload = [{
        exchange: isStock ? "NSE" : "NFO", // Simplified
        tradingSymbol: isStock ? `${finalSymbol}-EQ` : finalSymbol,
        price: parseFloat(price).toString(),
        qty: quantity.toString(),
        product: "MIS", // MIS for Intraday
        priceType: "L", // Limit
        triggerPrice: "",
        transType: side === "BUY" ? "B" : "S"
      }];
      
      const { data } = await api.post("/brokers/aliceblue/margin", payload);
      console.log("Margin API Response:", data);
      
      if (data && data.stat === "Ok" && data.result) {
        setMarginDetails({
          currentOrderMargin: data.result.marginUsed || "0.00"
        });
      } else {
        toast.error(`Could not fetch margin details: ${JSON.stringify(data)}`);
      }
    } catch (e) {
      console.error("Margin check failed:", e);
      let errMsg = "Margin check failed";
      if (e.response?.data?.detail) {
        errMsg = typeof e.response.data.detail === 'string' 
          ? e.response.data.detail 
          : JSON.stringify(e.response.data.detail);
      }
      toast.error(errMsg);
    } finally {
      setCheckingMargin(false);
    }
  };

  const clearForm = () => {
    setSymbol("");
    setQuantity(1);
    setPrice("");
    setMarginDetails(null);
    setSide("BUY");
    setExpiry("");
    setStrikePrice("");
    setCopyToUsers(true);
  };

  const placedOrder = async () => {
    if (!quantity || !price) {
      toast.error("Please fill quantity and price");
      return;
    }

    let finalSymbol = symbol;
    if (instrumentType === "futures") {
      finalSymbol = `${symbol}${expiry}FUT`;
    } else if (instrumentType === "option") {
      finalSymbol = `${symbol}${expiry}${strikePrice}${optionType}`;
    }

    try {
      setLoading(true);
      const payload = {
        side,
        qty: parseInt(quantity),
        price: parseFloat(price),
        symbol: finalSymbol,
        copy_to_users: copyToUsers
      };

      if (isBracket) {
        if (target) payload.target = parseFloat(target);
        if (stopLoss) payload.stop_loss = parseFloat(stopLoss);
      }

      await api.post("/orders", payload);
      toast.success("Order placed successfully!");

      // Reset form
      setSymbol("");
      setQuantity(1);
      setPrice("");
      setMarginDetails(null);
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
              symbol: finalSymbol
            };
            if (isBracket) {
              if (target) payload.target = parseFloat(target);
              if (stopLoss) payload.stop_loss = parseFloat(stopLoss);
            }
            await api.post("/orders", payload);
            toast.success("Mock Order placed successfully!");
            setSymbol("");
            setQuantity(1);
            setPrice("");
            setMarginDetails(null);
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

      <div className="mt-4 pt-4 border-t border-[var(--border)]">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
          <input
            type="checkbox"
            id="smartBracket1"
            checked={isBracket}
            onChange={(e) => setIsBracket(e.target.checked)}
            style={{ width: '16px', height: '16px', cursor: 'pointer' }}
          />
          <label htmlFor="smartBracket1" style={{ fontSize: '0.875rem', fontWeight: '600', color: 'var(--text-primary)', cursor: 'pointer' }}>
            Smart Bracket Order
          </label>
        </div>
        
        {isBracket && (
          <div className="grid grid-cols-2 gap-4 mt-2">
            <div>
              <label className="text-xs text-[var(--text-muted)]">Target (pts)</label>
              <input
                type="number"
                min="0"
                step="0.1"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                className="order-input !mt-1"
                placeholder="e.g. 20"
              />
            </div>
            <div>
              <label className="text-xs text-[var(--text-muted)]">Stop Loss (pts)</label>
              <input
                type="number"
                min="0"
                step="0.1"
                value={stopLoss}
                onChange={(e) => setStopLoss(e.target.value)}
                className="order-input !mt-1"
                placeholder="e.g. 10"
              />
            </div>
          </div>
        )}
      </div>
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

      <div className="mt-4 pt-4 border-t border-[var(--border)]">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
          <input
            type="checkbox"
            id="smartBracket2"
            checked={isBracket}
            onChange={(e) => setIsBracket(e.target.checked)}
            style={{ width: '16px', height: '16px', cursor: 'pointer' }}
          />
          <label htmlFor="smartBracket2" style={{ fontSize: '0.875rem', fontWeight: '600', color: 'var(--text-primary)', cursor: 'pointer' }}>
            Smart Bracket Order
          </label>
        </div>
        
        {isBracket && (
          <div className="grid grid-cols-2 gap-4 mt-2">
            <div>
              <label className="text-xs text-[var(--text-muted)]">Target (pts)</label>
              <input
                type="number"
                min="0"
                step="0.1"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                className="order-input !mt-1"
                placeholder="e.g. 20"
              />
            </div>
            <div>
              <label className="text-xs text-[var(--text-muted)]">Stop Loss (pts)</label>
              <input
                type="number"
                min="0"
                step="0.1"
                value={stopLoss}
                onChange={(e) => setStopLoss(e.target.value)}
                className="order-input !mt-1"
                placeholder="e.g. 10"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );

  if (isLightningMode) {
    return (
      <div className="h-full flex flex-col p-2">
        <div className="flex justify-end mb-2">
          <button 
            onClick={() => setIsLightningMode(false)}
            className="text-xs font-mono px-3 py-1 rounded bg-[var(--surface-hover)] hover:bg-[var(--border)] transition-colors"
          >
            Switch to Standard Order
          </button>
        </div>
        <div className="flex-1">
          <LightningScalper prices={prices} watchlist={watchlist} />
        </div>
      </div>
    );
  }

  return (
    <div className="quick-order-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', gap: '4px' }}>
        <div className="order-type-tabs" style={{ marginBottom: 0, flex: 1, display: 'flex', gap: '4px' }}>
          <button
            className={`order-type-btn ${instrumentType === "stock" ? "active" : ""}`}
            style={{ flex: 1, padding: '0.5rem 0.25rem', fontSize: '0.7rem' }}
            onClick={() => setInstrumentType("stock")}
          >
            Stocks
          </button>
          <button
            className={`order-type-btn ${instrumentType === "futures" ? "active" : ""}`}
            style={{ flex: 1, padding: '0.5rem 0.25rem', fontSize: '0.7rem' }}
            onClick={() => setInstrumentType("futures")}
          >
            Futures
          </button>
          <button
            className={`order-type-btn ${instrumentType === "option" ? "active" : ""}`}
            style={{ flex: 1, padding: '0.5rem 0.25rem', fontSize: '0.7rem' }}
            onClick={() => setInstrumentType("option")}
          >
            Options
          </button>
        </div>
        <button 
          onClick={() => setIsLightningMode(true)}
          className="text-xs font-mono px-2 py-1 rounded border border-yellow-500/30 text-yellow-500 hover:bg-yellow-500/10 flex items-center justify-center transition-colors"
          style={{ height: '32px', minWidth: '32px' }}
          title="Lightning Scalper Mode"
        >
          <Lightning size={16} weight="fill" />
        </button>
        
        <button 
          onClick={clearForm}
          title="Clear Form"
          style={{ 
            background: 'transparent', 
            border: '1px solid var(--border)', 
            padding: '0.5rem', 
            borderRadius: '0.375rem', 
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
          onMouseEnter={(e) => e.currentTarget.style.color = 'var(--text-primary)'}
          onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-secondary)'}
        >
          <ArrowCounterClockwise size={16} weight="bold" />
        </button>
      </div>

      <div className="order-form">
        {instrumentType === "stock" && renderStockForm()}
        {instrumentType === "futures" && renderFuturesForm()}
        {instrumentType === "option" && renderOptionsForm()}

        {marginDetails && (
          <div className="margin-details">
            <div className="margin-row">
              <span className="margin-label">Required Margin</span>
              <span className="margin-value">₹{marginDetails.currentOrderMargin}</span>
            </div>
          </div>
        )}

        <div style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <input 
            type="checkbox" 
            id="copyToUsers"
            checked={copyToUsers}
            onChange={(e) => setCopyToUsers(e.target.checked)}
            style={{ width: '16px', height: '16px', cursor: 'pointer' }}
          />
          <label htmlFor="copyToUsers" style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
            Copy trade to all managed users
          </label>
        </div>

        <div className="order-actions" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '20px' }}>
          <button
            onClick={checkMargin}
            disabled={checkingMargin}
            className="check-margin-btn"
            style={{ 
              backgroundColor: 'transparent', 
              color: 'var(--text-primary)', 
              border: '1px solid var(--border-focus, #3b82f6)', 
              padding: '0.75rem', 
              borderRadius: '0.375rem', 
              cursor: 'pointer',
              fontWeight: '600',
              fontSize: '0.875rem'
            }}
          >
            {checkingMargin ? "Checking..." : "Check Margin"}
          </button>
          
          <button
            onClick={placedOrder}
            disabled={loading}
            className="place-order-btn"
            style={{ marginTop: 0 }}
          >
            <CheckCircle size={16} />
            <span>{loading ? "Placing..." : "Place Order"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
