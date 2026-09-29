import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useSymbol } from "@/lib/symbol-context";
import ChartWidget from "@/components/ChartWidget";

export default function Chart() {
  const [symbols, setSymbols] = useState([]);
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [layout, setLayout] = useState(1); // 1, 2, or 4
  const [dataSource, setDataSource] = useState(() => {
    const now = new Date();
    // Assuming local browser time is IST
    if (now.getHours() > 17 || (now.getHours() === 17 && now.getMinutes() >= 30)) {
      return "aliceblue";
    }
    return "parquet";
  });
  const { setGlobalSymbol } = useSymbol();
  
  // Historical filters
  const [fromDate, setFromDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 7); // Default to last 7 days
    return d.toISOString().split("T")[0];
  });
  const [toDate, setToDate] = useState(() => new Date().toISOString().split("T")[0]);
  
  const [inputFrom, setInputFrom] = useState(fromDate);
  const [inputTo, setInputTo] = useState(toDate);
  const [interval, setIntervalVal] = useState("1"); // 1, 5, 15, D

  useEffect(() => {
    const loadSymbols = async () => {
      try {
        const { data } = await api.get("/market/symbols");
        const allSyms = Array.from(new Set([...(data.nifty50 || []), ...(data.symbols || [])]));
        setSymbols(allSyms);
        if (allSyms.length > 0 && !selectedSymbol) {
          setSelectedSymbol("NIFTY");
        }
      } catch (e) {
        console.error("Failed to load symbols", e);
      }
    };
    loadSymbols();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const chartConfigs = [];
  if (layout >= 1) chartConfigs.push({ id: 0, isPrimary: true, defaultSymbol: selectedSymbol || "NIFTY" });
  if (layout >= 2) chartConfigs.push({ id: 1, isPrimary: false, defaultSymbol: "BANKNIFTY" });
  if (layout >= 4) {
    chartConfigs.push({ id: 2, isPrimary: false, defaultSymbol: "FINNIFTY" });
    chartConfigs.push({ id: 3, isPrimary: false, defaultSymbol: "RELIANCE" });
  }

  const gridClass = layout === 1 ? "grid-cols-1" : layout === 2 ? "grid-cols-2" : "grid-cols-2 grid-rows-2";

  return (
    <div className="space-y-1 w-full flex flex-col overflow-hidden" data-testid="chart-page" style={{ height: "calc(100vh - 120px)" }}>
      <div className="flex items-center justify-between gap-4">
        <h1 className="whitespace-nowrap shrink-0" style={{ fontFamily: "Chivo", fontWeight: 800, fontSize: 20, letterSpacing: "-0.02em" }}>Market Chart.</h1>
        
        <div className="flex items-center gap-2 justify-end overflow-hidden">
          
          <div className="flex items-center shrink-0 p-1 rounded gap-1" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
             <button className={`px-2 py-0.5 text-[11px] font-bold rounded ${layout === 1 ? "bg-[var(--brand)] text-white" : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"}`} onClick={() => setLayout(1)}>1x</button>
             <button className={`px-2 py-0.5 text-[11px] font-bold rounded ${layout === 2 ? "bg-[var(--brand)] text-white" : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"}`} onClick={() => setLayout(2)}>2x</button>
             <button className={`px-2 py-0.5 text-[11px] font-bold rounded ${layout === 4 ? "bg-[var(--brand)] text-white" : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"}`} onClick={() => setLayout(4)}>4x</button>
          </div>

          <div className="hidden lg:flex shrink-0 overflow-hidden p-1 rounded" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
             <button 
                className={`px-3 py-1 text-xs font-bold rounded whitespace-nowrap ${dataSource === "parquet" ? "bg-[var(--brand)] text-white" : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"}`}
                onClick={() => setDataSource("parquet")}
             >
               Live
             </button>
             <button 
                className={`px-3 py-1 text-xs font-bold rounded whitespace-nowrap ${dataSource === "aliceblue" ? "bg-[var(--brand)] text-white" : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"}`}
                onClick={() => setDataSource("aliceblue")}
             >
               Historical
             </button>
          </div>


        </div>
      </div>

      {dataSource === "aliceblue" && (
          <div className="flex items-end gap-3 px-3 py-1.5 rounded mb-1 shrink-0" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
             <div>
               <div className="text-[9px] uppercase tracking-wider mb-0.5 font-bold" style={{ color: "var(--text-secondary)" }}>From Date</div>
               <input type="date" className="terminal px-2 py-0.5 rounded text-xs outline-none h-[26px]" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} value={inputFrom} onChange={(e) => setInputFrom(e.target.value)} />
             </div>
             <div>
               <div className="text-[9px] uppercase tracking-wider mb-0.5 font-bold" style={{ color: "var(--text-secondary)" }}>To Date (Optional)</div>
               <input type="date" className="terminal px-2 py-0.5 rounded text-xs outline-none h-[26px]" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} value={inputTo} onChange={(e) => setInputTo(e.target.value)} />
             </div>
             <button 
               className="btn btn-primary px-4 font-bold mono uppercase tracking-widest flex items-center justify-center"
               style={{ height: '26px', fontSize: '10px' }}
               onClick={() => {
                 setFromDate(inputFrom);
                 setToDate(inputTo || inputFrom);
               }}
             >
               Load
             </button>
          </div>
        )}
  
        <div className={`flex-1 relative grid gap-2 ${gridClass}`} style={{ minHeight: 0, height: 0 }}>
        {chartConfigs.map((cfg) => (
          <ChartWidget 
            key={cfg.id}
            initialSymbol={cfg.defaultSymbol}
            symbols={symbols}
            globalDataSource={dataSource}
            globalInterval={interval}
            fromDate={fromDate}
            toDate={toDate}
            isPrimary={cfg.isPrimary}
          />
        ))}
      </div>
    </div>
  );
}
