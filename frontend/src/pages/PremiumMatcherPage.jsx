import { useState, useEffect } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/use-polling";
import PremiumMatcher from "@/components/options/PremiumMatcher";

export default function PremiumMatcherPage() {
  const [symbol, setSymbol] = useState("NIFTY");
  const [equities, setEquities] = useState([]);
  const [indices, setIndices] = useState(["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "NIFTYNXT50"]);

  useEffect(() => {
    api.get("/market/symbols").then(({ data }) => {
      const eqs = data.nifty50 || [];
      const inds = (data.symbols || []).filter((s) => !eqs.includes(s));
      if (eqs.length) setEquities(eqs);
      if (inds.length) setIndices(inds);
    }).catch(console.error);
  }, []);

  const { data: chain, isValidating } = usePolling(`/analytics/option-chain?symbol=${symbol}`, { intervalMs: 3000 });

  return (
    <div className="p-4 space-y-4 max-w-7xl">
      <div className="flex items-center gap-4 mb-6">
        <h1 style={{ fontFamily: "Outfit", fontWeight: 700, fontSize: 28, letterSpacing: "-0.01em" }}>Premium Matcher</h1>
        
        <div className="flex items-center gap-2">
          <select 
            value={indices.includes(symbol) ? "" : symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="terminal !w-auto !py-1 !text-sm cursor-pointer"
          >
            <option disabled value="" className="bg-[var(--surface)] text-[var(--text-primary)]">Equities</option>
            {equities.map((s) => <option key={s} value={s} className="bg-[var(--surface)] text-[var(--text-primary)]">{s}</option>)}
          </select>
          
          <select 
            value={indices.includes(symbol) ? symbol : ""}
            onChange={(e) => setSymbol(e.target.value)}
            className="terminal !w-auto !py-1 !text-sm cursor-pointer"
          >
            <option disabled value="" className="bg-[var(--surface)] text-[var(--text-primary)]">── Indices ──</option>
            {indices.map((s) => <option key={s} value={s} className="bg-[var(--surface)] text-[var(--text-primary)]">{s}</option>)}
          </select>
        </div>
      </div>

      {!chain ? (
        <div className="dim text-sm mt-8">Loading premium pairs for {symbol}...</div>
      ) : (
        <div className={`transition-opacity duration-200 ${isValidating ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>
          <PremiumMatcher chain={chain} symbol={symbol} />
        </div>
      )}
    </div>
  );
}
