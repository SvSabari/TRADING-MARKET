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
          const { data } = await api.get(`/parquet/preview?path=${encodeURIComponent(localSymbol)}&limit=1000&interval=${localInterval}`);
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
        style={{ background: "var(--surface)", border: "1px solid var(--border)", color: INDICES.includes(localSymbol) ? "var(--brand)" : "var(--text-secondary)", fontSize: "11px", padding: "2px 4px" }}
        value={INDICES.includes(localSymbol) ? localSymbol : ""}
        onChange={(e) => setLocalSymbol(e.target.value)}
      >
        <option value="" disabled>Index...</option>
        {symbols.filter(s => INDICES.includes(s)).map(s => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>

      <select 
        className="outline-none cursor-pointer font-bold uppercase rounded shadow-sm"
        style={{ background: "var(--surface)", border: "1px solid var(--border)", color: !INDICES.includes(localSymbol) ? "var(--brand)" : "var(--text-secondary)", fontSize: "11px", padding: "2px 4px" }}
        value={!INDICES.includes(localSymbol) ? localSymbol : ""}
        onChange={(e) => setLocalSymbol(e.target.value)}
      >
        <option value="" disabled>Stock...</option>
        {symbols.filter(s => !INDICES.includes(s)).map(s => (
          <option key={s} value={s}>{s}</option>
        ))}
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

      <button 
        onClick={() => setShowTape(!showTape)}
        className="ml-1 p-1 rounded hover:bg-[var(--surface-hover)] transition-colors flex items-center justify-center"
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
              <CandleChart key={`${localSymbol}-${globalDataSource}-${localInterval}`} data={chartData} symbol={localSymbol} interval={localInterval} />
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
    </Panel>
  );
}
