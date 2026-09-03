import { useState } from "react";
import { Lightning, TrendUp, TrendDown } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { toast } from "sonner";

export default function LightningScalper({ prices, watchlist = [] }) {
  const defaultSymbol = watchlist.length > 0 ? watchlist[0] : "RELIANCE";
  const [symbol, setSymbol] = useState(defaultSymbol);
  const [quantity, setQuantity] = useState(1);
  const [loading, setLoading] = useState(false);

  const ltp = prices[symbol]?.ltp || 0;
  
  const executeOrder = async (side) => {
    if (!symbol || !quantity) return;
    
    setLoading(true);
    try {
      const payload = {
        symbol: symbol,
        side: side,
        quantity: parseInt(quantity, 10),
        price: ltp,
        order_type: "MARKET",
        product: "MIS",
        copy_to_users: true
      };
      
      const res = await api.post("/orders", payload);
      toast.success(`${side} ${quantity} ${symbol} @ MKT submitted!`);
    } catch (e) {
      toast.error(`Order Failed: ${e.response?.data?.detail || e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-[var(--surface)] p-4 rounded-xl border border-[var(--border)] relative overflow-hidden">
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-yellow-400 to-orange-500 opacity-80" />
      
      <div className="flex items-center justify-between mb-6">
        <h3 className="font-bold text-lg flex items-center gap-2" style={{ fontFamily: "Chivo", letterSpacing: "-0.02em" }}>
          <Lightning size={24} weight="fill" className="text-yellow-400 drop-shadow" />
          Scalper Mode
        </h3>
        <select 
          className="bg-[var(--surface-hover)] border border-[var(--border)] px-3 py-1.5 rounded-lg font-mono text-sm outline-none w-32"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
        >
          {watchlist.map(s => <option key={s} value={s}>{s}</option>)}
          {watchlist.length === 0 && <option value="RELIANCE">RELIANCE</option>}
        </select>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center gap-8">
        <div className="text-center">
          <div className="text-[10px] uppercase tracking-widest dim font-mono mb-2">Live Price</div>
          <div className={`text-5xl font-black font-mono tracking-tighter ${ltp > 0 ? 'text-[var(--text-primary)]' : 'dim'}`}>
            {ltp > 0 ? `₹${ltp.toFixed(2)}` : "---"}
          </div>
        </div>

        <div className="w-full space-y-4">
          <div className="flex items-center gap-2 overflow-x-auto pb-2 custom-scrollbar justify-center">
            {[1, 5, 10, 25, 50, 100].map(q => (
              <button 
                key={q}
                onClick={() => setQuantity(q)}
                className={`px-3 py-2 rounded-lg text-sm font-mono transition-all ${quantity === q ? 'bg-[var(--brand)] text-white shadow-md font-bold' : 'bg-[var(--surface-hover)] hover:bg-[var(--border)] dim'}`}
              >
                {q}
              </button>
            ))}
          </div>

          <div className="flex gap-4 w-full h-28 pt-2">
            <button 
              onClick={() => executeOrder("BUY")}
              disabled={loading || ltp === 0}
              className="flex-1 rounded-2xl flex flex-col items-center justify-center gap-1 font-bold text-2xl text-white transition-all transform hover:-translate-y-1 active:translate-y-1 active:scale-95 shadow-xl disabled:opacity-50 disabled:transform-none"
              style={{ backgroundColor: "var(--buy)", fontFamily: "Chivo" }}
            >
              <TrendUp size={32} weight="bold" />
              BUY
            </button>
            
            <button 
              onClick={() => executeOrder("SELL")}
              disabled={loading || ltp === 0}
              className="flex-1 rounded-2xl flex flex-col items-center justify-center gap-1 font-bold text-2xl text-white transition-all transform hover:-translate-y-1 active:translate-y-1 active:scale-95 shadow-xl disabled:opacity-50 disabled:transform-none"
              style={{ backgroundColor: "var(--sell)", fontFamily: "Chivo" }}
            >
              <TrendDown size={32} weight="bold" />
              SELL
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
