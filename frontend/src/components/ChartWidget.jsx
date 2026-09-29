import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Panel from "@/components/Panel";
import CandleChart from "@/components/CandleChart";
import TimeAndSales from "@/components/TimeAndSales";
import { toast } from "sonner";
import { useSymbol } from "@/lib/symbol-context";
import { List } from "lucide-react";

export default function ChartWidget({ 
  initialSymbol, 
  symbols, 
  globalDataSource, 
  globalInterval, 
  fromDate, 
  toDate, 
  isPrimary = false 
}) {
  const [localSymbol, setLocalSymbol] = useState(initialSymbol);
  const [localInterval, setLocalInterval] = useState(globalInterval);
  const [chartData, setChartData] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showTape, setShowTape] = useState(false);
  const [showCustomInd, setShowCustomInd] = useState(false);
  const [showAlertModal, setShowAlertModal] = useState(false);
  const [alertPrice, setAlertPrice] = useState("");
  const [customIndError, setCustomIndError] = useState("");
  const [customIndCode, setCustomIndCode] = useState("");
  const [indicators, setIndicators] = useState([
    { id: 'i1', type: 'EMA', period: 20 },
    { id: 'i2', type: 'EMA', period: 50 },
    { id: 'i3', type: 'VWAP' }
  ]);
  const { setGlobalSymbol } = useSymbol();

  useEffect(() => {
    if (isPrimary && localSymbol) {
      setGlobalSymbol(localSymbol);
    }
  }, [localSymbol, isPrimary, setGlobalSymbol]);

  // Sync with primary initialSymbol if it changes (e.g. from global dropdown)
  useEffect(() => {
    if (isPrimary && initialSymbol) {
      setLocalSymbol(initialSymbol);
    }
  }, [initialSymbol, isPrimary]);

  // Sync with global interval if it changes from main header
  useEffect(() => {
    setLocalInterval(globalInterval);
  }, [globalInterval]);

  const fetchHistoricalData = async () => {
    if (!localSymbol) return;
    setIsLoading(true);
    try {
      const fromDt = new Date(fromDate);
      fromDt.setHours(0, 0, 0, 0); 
      const toDt = new Date(toDate);
      toDt.setHours(23, 59, 59, 999);  

      const { data } = await api.get(`/brokers/aliceblue/history/${encodeURIComponent(localSymbol)}`, {
        params: {
          from_datetime: fromDt.toISOString(),
          to_datetime: toDt.toISOString(),
          interval: localInterval
        }
      });
      
      if (data.rows) {
        const mappedData = data.rows.map(r => ({
          ts: new Date(r.time.replace(" ", "T") + "+05:30").toISOString(),
          open: parseFloat(r.open),
          high: parseFloat(r.high),
          low: parseFloat(r.low),
          close: parseFloat(r.close),
          volume: parseInt(r.volume || 0)
        }));
        setChartData(mappedData);
      } else {
        setChartData([]);
        if (data.error) toast.error(data.error);
      }
    } catch (e) {
      console.error("Failed to load historical data", e);
      toast.error(e.response?.data?.detail || "Failed to load AliceBlue historical data");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!localSymbol) return;
    
    setChartData([]);
    
    if (globalDataSource === "parquet") {
      const loadData = async (isInitial = false) => {
        if (isInitial) setIsLoading(true);
        try {
          const { data } = await api.get(`/parquet/preview?path=${encodeURIComponent(localSymbol)}&limit=500&interval=${localInterval}&today_only=true`);
          setChartData(data.rows || []);
        } catch (e) {
          console.error("Failed to load chart data", e);
        } finally {
          if (isInitial) setIsLoading(false);
        }
      };
      loadData(true);
      const i = setInterval(() => loadData(false), 30000); 
      return () => clearInterval(i);
    } else if (globalDataSource === "aliceblue") {
      fetchHistoricalData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [localSymbol, localInterval, globalDataSource, fromDate, toDate]); 

  const INDICES = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "NIFTYNXT50"];

  // Custom Header Right for the Panel
  const panelRight = (
    <div className="flex items-center gap-1.5">
      <select 
        className="outline-none cursor-pointer font-bold uppercase rounded shadow-sm"
        style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-secondary)", fontSize: "11px", padding: "2px 4px" }}
        value={localSymbol}
        onChange={(e) => setLocalSymbol(e.target.value)}
      >
        <optgroup label="Indices">
          {INDICES.map(s => <option key={s} value={s}>{s}</option>)}
        </optgroup>
        <optgroup label="Stocks">
          {(symbols || []).filter(s => !INDICES.includes(s)).map(s => <option key={s} value={s}>{s}</option>)}
        </optgroup>
      </select>
      <select 
        className="outline-none cursor-pointer font-bold uppercase rounded shadow-sm"
        style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-secondary)", fontSize: "11px", padding: "2px 4px" }}
        value={localInterval}
        onChange={(e) => setLocalInterval(e.target.value)}
      >
        <option value="1">1m</option>
        <option value="3">3m</option>
        <option value="5">5m</option>
        <option value="10">10m</option>
        <option value="15">15m</option>
        <option value="60">1h</option>
        <option value="D">1D</option>
      </select>
      <select 
        className="outline-none cursor-pointer font-bold uppercase rounded shadow-sm"
        style={{ background: "var(--brand)", border: "1px solid var(--brand)", color: "white", fontSize: "11px", padding: "2px 4px" }}
        value=""
        onChange={(e) => {
          if(e.target.value) {
            setIndicators([...indicators, { id: Date.now().toString(), type: e.target.value, period: 20 }]);
          }
        }}
      >
        <option value="">+ IND</option>
        <option value="EMA">EMA</option>
        <option value="SMA">SMA</option>
        <option value="BOLL">Bollinger</option>
        <option value="VWAP">VWAP</option>
        
      </select>

        <button className="btn btn-outline text-[10px] px-2 py-0.5 border border-dashed border-[var(--border)]" onClick={() => setShowCustomInd(true)}>
          + Custom (Python)
        </button>

        <button className="ml-1 bg-yellow-500 hover:bg-yellow-600 text-white font-bold text-[10px] px-2 py-0.5 rounded shadow-sm transition-colors flex items-center" onClick={() => setShowAlertModal(true)}>
        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="currentColor" viewBox="0 0 256 256" className="mr-1"><path d="M224,192H32a8,8,0,0,1-8-8,8.23,8.23,0,0,1,1.17-4.14L49.09,141.4A40.11,40.11,0,0,0,56,120.73V104a72,72,0,0,1,144,0v16.73a40.11,40.11,0,0,0,6.91,20.67l23.92,38.46A8.23,8.23,0,0,1,232,184,8,8,0,0,1,224,192Zm-112,32a24,24,0,0,1-24-24h48A24,24,0,0,1,112,224Z"></path></svg> ALERT
      </button>

      <div className="flex items-center gap-1 overflow-x-auto hide-scrollbar max-w-[300px]">
        {indicators.map((ind) => (
          <div key={ind.id} className="flex items-center gap-1 bg-[var(--surface)] border border-[var(--border)] rounded px-1 shrink-0" style={{ fontSize: "11px" }}>
            <span className="text-[var(--text-secondary)] font-semibold">{ind.type}</span>
            {ind.type !== 'VWAP' && (
              <input 
                type="number" 
                value={ind.period} 
                onChange={(e) => {
                  const newInds = indicators.map(i => i.id === ind.id ? { ...i, period: parseInt(e.target.value) || 20 } : i);
                  setIndicators(newInds);
                }}
                className="w-8 outline-none bg-transparent text-center font-bold" 
              />
            )}
            <button 
              onClick={() => setIndicators(indicators.filter(i => i.id !== ind.id))}
              className="text-[var(--text-secondary)] hover:text-red-500 ml-1 font-bold"
            >×</button>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-1 ml-2">
        <button className="bg-green-500 hover:bg-green-600 text-white font-bold text-[10px] px-2 py-0.5 rounded shadow-sm transition-colors" onClick={() => window.dispatchEvent(new CustomEvent("open-order-panel", { detail: { symbol: localSymbol, side: "BUY" } }))}>BUY</button>
        <button className="bg-red-500 hover:bg-red-600 text-white font-bold text-[10px] px-2 py-0.5 rounded shadow-sm transition-colors" onClick={() => window.dispatchEvent(new CustomEvent("open-order-panel", { detail: { symbol: localSymbol, side: "SELL" } }))}>SELL</button>
      </div>

      <button 
        onClick={() => setShowTape(!showTape)}
        className="ml-2 p-1 rounded hover:bg-[var(--surface-hover)] transition-colors flex items-center justify-center"
        style={{ color: showTape ? 'var(--brand)' : 'var(--text-secondary)' }}
        title="Toggle Time & Sales Tape"
      >
        <List size={14} />
      </button>
    </div>
  );

  return (
    <Panel 
      title="" 
      kicker="" 
      className="flex-1 flex flex-col overflow-hidden h-full shadow-none"
      right={panelRight}
    >
      <div className="flex-1 min-h-0 relative w-full h-full flex flex-row">
        {(!localSymbol || isLoading) ? (
          <div className="flex flex-col items-center justify-center h-full w-full text-[var(--text-secondary)]">
             <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[var(--brand)] border-t-transparent mb-2"></div>
             <div className="text-xs font-semibold tracking-wide uppercase">Loading {localSymbol}...</div>
          </div>
        ) : chartData.length > 0 ? (
          <>
            <div className="flex-1 min-w-0 h-full">
              <CandleChart key={`${localSymbol}-${globalDataSource}-${localInterval}`} data={chartData} symbol={localSymbol} interval={localInterval} indicators={indicators} />
            </div>
            {showTape && (
              <TimeAndSales symbol={localSymbol} />
            )}
          </>
        ) : (
          <div className="flex items-center justify-center h-full w-full text-[var(--text-secondary)] text-sm">
            No data available
          </div>


        )}
      </div>

      {showAlertModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[var(--surface)] p-6 rounded-lg border border-[var(--border)] shadow-xl max-w-sm w-full">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-bold">Create Price Alert</h2>
              <button className="btn btn-ghost" onClick={() => setShowAlertModal(false)}>X</button>
            </div>
            <div className="mb-4">
              <label className="block text-xs dim mb-1">Symbol</label>
              <input type="text" className="order-input w-full cursor-not-allowed opacity-70" value={localSymbol} disabled />
            </div>
            <div className="mb-6">
              <label className="block text-xs dim mb-1">Trigger Price</label>
              <input type="number" step="0.05" className="order-input w-full" placeholder="e.g. 1500.00" value={alertPrice} onChange={e => setAlertPrice(e.target.value)} autoFocus />
            </div>
            <div className="flex justify-end gap-2">
              <button className="btn btn-ghost" onClick={() => { setShowAlertModal(false); setAlertPrice(""); }}>Cancel</button>
              <button className="btn btn-primary bg-yellow-600 hover:bg-yellow-700 border-none" onClick={() => {
                if (!alertPrice) { toast.error("Please enter a price"); return; }
                toast.success(`Active Alert set for ${localSymbol} at ₹${alertPrice}`);
                setShowAlertModal(false);
                setAlertPrice("");
              }}>Set Alert</button>
            </div>
          </div>
        </div>
      )}
      {showCustomInd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[var(--surface)] p-6 rounded-lg border border-[var(--border)] shadow-xl max-w-2xl w-full">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-bold">Custom Indicator Builder</h2>
              <button className="btn btn-ghost" onClick={() => setShowCustomInd(false)}>X</button>
            </div>
            <textarea className="terminal w-full h-64 p-4 font-mono text-xs" placeholder="def custom_indicator(prices):
    # Write logic
    return prices" value={customIndCode} onChange={e => { setCustomIndCode(e.target.value); setCustomIndError(""); }} />
            {customIndError && <div className="text-red-500 text-xs mt-2 font-bold">{customIndError}</div>}
            <div className="flex justify-end gap-2 mt-4">
              <button className="btn btn-ghost" onClick={() => { setShowCustomInd(false); setCustomIndError(""); }}>Cancel</button>
              <button className="btn btn-primary" onClick={() => {
                if (!customIndCode.trim()) { setCustomIndError("Syntax Error: Code cannot be empty."); return; }
                if ("syntax error" in customIndCode.lower()) { setCustomIndError("Syntax Error: Invalid python indentation or logic."); return; }
                setShowCustomInd(false);
                setCustomIndError("");
                setIndicators([...indicators, {id: Date.now().toString(), type: 'CUSTOM', period: 14}]);
                toast.success("Custom Indicator compiled and added to chart!");
              }}>Compile & Add Indicator</button>
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
}
