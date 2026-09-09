import { useState, useEffect } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import PremiumMatcher from "@/components/options/PremiumMatcher";

export default function PremiumMatcherPage() {
  const [preset, setPreset] = useState("indices");
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

  return (
    <div className="p-4 space-y-4 max-w-7xl">
      <div className="flex items-center gap-4 mb-6">
        <h1 style={{ fontFamily: "Outfit", fontWeight: 700, fontSize: 28, letterSpacing: "-0.01em" }}>Premium Matcher</h1>
        
        <div className="flex items-center gap-2">
          <select 
            value={preset}
            onChange={(e) => setPreset(e.target.value)}
            className="terminal !w-auto !py-1 !text-sm cursor-pointer"
          >
            <option value="indices" className="font-bold text-[var(--brand)]">All Indices (Separate)</option>
            <option value="all" className="font-bold text-[var(--brand)]">All Market (Combined Table)</option>
            
            <optgroup label="Indices" className="dim">
              {indices.map((s) => <option key={s} value={s}>{s}</option>)}
            </optgroup>
            
            <optgroup label="Equities" className="dim">
              {equities.map((s) => <option key={s} value={s}>{s}</option>)}
            </optgroup>
          </select>
        </div>
      </div>

      {preset === "indices" ? (
        <div className="space-y-6">
          {indices.map(idx => (
            <PremiumMatcher key={idx} preset={idx} showSymbolColumn={false} />
          ))}
        </div>
      ) : (
        <PremiumMatcher preset={preset} showSymbolColumn={preset === "all"} />
      )}
    </div>
  );
}
