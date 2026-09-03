import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import Panel from "@/components/Panel";
import { Plus, Trash } from "@phosphor-icons/react";

export default function Strategies() {
  const [kinds, setKinds] = useState([]);
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ name: "", kind: "ema_crossover", symbols: "", copy_to_users: true });
  const [symbolsList, setSymbolsList] = useState([]);
  const [showSymbolDropdown, setShowSymbolDropdown] = useState(false);

  const load = async () => {
    // Load kinds and strategies immediately — these are fast DB queries
    const [a, b] = await Promise.all([api.get("/strategies/kinds"), api.get("/strategies")]);
    setKinds(a.data.kinds);
    setItems(b.data.strategies);
    // Load symbols list in the background — market snapshot can be slow
    api.get("/market/snapshot").catch(() => ({ data: { ticks: [] } })).then(c => {
      if (c?.data?.ticks) setSymbolsList(c.data.ticks.map(t => t.symbol));
    });
  };
  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    if (!form.name) return toast.error("Name required");
    try {
      await api.post("/strategies", {
        name: form.name, kind: form.kind, enabled: false,
        copy_to_users: form.copy_to_users,
        symbols: form.symbols.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean),
        params: {
          interval_seconds: parseInt(form.interval_seconds) || 15,
          qty: parseInt(form.qty) || 1
        },
      });
      toast.success("Strategy created");
      setForm({ ...form, name: "" });
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const toggleSymbol = (sym) => {
    const current = form.symbols ? form.symbols.split(",").map(s => s.trim()).filter(Boolean) : [];
    if (current.includes(sym)) {
      setForm({ ...form, symbols: current.filter(s => s !== sym).join(",") });
    } else {
      setForm({ ...form, symbols: [...current, sym].join(",") });
    }
  };

  const toggle = async (s) => {
    await api.patch(`/strategies/${s.id}`, { enabled: !s.enabled });
    load();
  };
  const del = async (s) => {
    await api.delete(`/strategies/${s.id}`);
    toast.success("Strategy removed");
    load();
  };

  return (
    <div className="space-y-4" data-testid="strategies-page">
      <div>
        <h1 style={{ fontFamily: "Outfit", fontWeight: 700, fontSize: 28, letterSpacing: "-0.01em" }}>Strategy manager</h1>
        <p className="dim text-sm mt-1">Enable, configure and combine algorithmic strategies. Mock execution only.</p>
      </div>
      <Panel title="Create Strategy" kicker="configure & launch">
        <div className="p-4 grid grid-cols-1 md:grid-cols-3 xl:grid-cols-6 gap-4">
          <input className="terminal md:col-span-3 xl:col-span-2" data-testid="strategy-name-input" placeholder="Strategy Nickname" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <select className="terminal" data-testid="strategy-kind-select" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
            {kinds.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
          </select>
          <div className="relative">
            <div 
              className="terminal cursor-pointer min-h-[38px] flex items-center overflow-hidden whitespace-nowrap" 
              onClick={() => setShowSymbolDropdown(!showSymbolDropdown)}
            >
              {form.symbols || <span className="dim">Select Symbols...</span>}
            </div>
            {showSymbolDropdown && (
              <div className="absolute top-full left-0 w-64 max-h-64 overflow-y-auto bg-white border border-gray-300 z-50 p-2 shadow-xl">
                <div className="text-xs mb-2 dim flex justify-between">
                  <span>Select Stocks:</span>
                  <button onClick={(e) => { e.stopPropagation(); setShowSymbolDropdown(false); }} className="hover:text-white">Close</button>
                </div>
                {symbolsList.map(sym => {
                  const isSelected = form.symbols.split(",").map(s => s.trim()).includes(sym);
                  return (
                    <label key={sym} className="flex items-center px-2 py-1 hover:bg-gray-100 cursor-pointer text-sm">
                      <input 
                        type="checkbox" 
                        checked={isSelected}
                        onChange={() => toggleSymbol(sym)}
                        className="mr-2"
                      />
                      {sym}
                    </label>
                  );
                })}
              </div>
            )}
          </div>
          <input className="terminal" type="number" min="5" placeholder="Interval (sec)" value={form.interval_seconds} data-testid="strategy-interval-input" onChange={(e) => setForm({ ...form, interval_seconds: e.target.value })} />
          <input className="terminal" type="number" min="1" placeholder="Quantity" value={form.qty} data-testid="strategy-qty-input" onChange={(e) => setForm({ ...form, qty: e.target.value })} />
          <div className="md:col-span-3 xl:col-span-6 flex items-center gap-2 mt-2">
            <input 
              type="checkbox" 
              id="stratCopyToUsers"
              checked={form.copy_to_users}
              onChange={(e) => setForm({ ...form, copy_to_users: e.target.checked })}
              className="cursor-pointer"
            />
            <label htmlFor="stratCopyToUsers" className="text-xs dim cursor-pointer">
              Mirror strategy trades to all managed users
            </label>
          </div>
          <button className="btn btn-primary md:col-span-3 xl:col-span-6 justify-center mt-2" data-testid="strategy-create-btn" onClick={create}><Plus size={14} weight="bold" /> Create</button>
        </div>
      </Panel>

      <Panel title="My Strategies" kicker={`${items.length} instances`}>
        <table className="w-full text-xs">
          <thead><tr className="dim text-[10px] uppercase tracking-widest border-b border-[#222]">
            <th className="text-left py-2 px-4">Name</th>
            <th className="text-left py-2 px-4">Kind</th>
            <th className="text-left py-2 px-4">Symbols</th>
            <th className="text-right py-2 px-4">Interval</th>
            <th className="text-right py-2 px-4">Fires</th>
            <th className="text-center py-2 px-4">Status</th>
            <th className="text-right py-2 px-4">Actions</th>
          </tr></thead>
          <tbody className="cell-divider">
            {items.map((s) => (
              <tr key={s.id} data-testid={`strategy-row-${s.id}`}>
                <td className="py-2 px-4">{s.name}</td>
                <td className="py-2 px-4 mono dim">{s.kind}</td>
                <td className="py-2 px-4 mono">{s.symbols.join(", ") || "—"}</td>
                <td className="py-2 px-4 text-right num dim">{s.params?.interval_seconds ?? 15}s</td>
                <td className="py-2 px-4 text-right num buy">{s.fire_count || 0}</td>
                <td className="py-2 px-4 text-center">
                  <button className={`btn ${s.enabled ? "btn-primary" : ""}`} data-testid={`strategy-toggle-${s.id}`} onClick={() => toggle(s)}>
                    {s.enabled ? "RUNNING" : "PAUSED"}
                  </button>
                </td>
                <td className="py-2 px-4 text-right">
                  <button className="btn btn-danger" data-testid={`strategy-delete-${s.id}`} onClick={() => del(s)}>
                    <Trash size={14} weight="bold" />
                  </button>
                </td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={7} className="p-8 text-center dim text-xs">No strategies yet. Create one above.</td></tr>}
          </tbody>
        </table>
      </Panel>

      <Panel title="Available Strategy Library" kicker={`${kinds.length} strategies`}>
        <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {kinds.map((k) => {
            const catColors = {
              trend:    { bg: "rgba(59,130,246,0.10)",  border: "#3b82f6", text: "#3b82f6", label: "TREND" },
              reversal: { bg: "rgba(168,85,247,0.10)",  border: "#a855f7", text: "#a855f7", label: "REVERSAL" },
              breakout: { bg: "rgba(234,179,8,0.10)",   border: "#eab308", text: "#eab308", label: "BREAKOUT" },
              momentum: { bg: "rgba(239,68,68,0.10)",   border: "#ef4444", text: "#ef4444", label: "MOMENTUM" },
              scalping: { bg: "rgba(20,184,166,0.10)",  border: "#14b8a6", text: "#14b8a6", label: "SCALPING" },
            };
            const cat = catColors[k.category] || catColors.trend;
            return (
              <div key={k.id} style={{ background: "var(--surface)", border: `1.5px solid ${cat.border}`, borderRadius: 12, padding: "16px 18px", display: "flex", flexDirection: "column", gap: 8, transition: "box-shadow 0.18s" }}
                className="hover:shadow-lg">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div style={{ fontFamily: "Outfit", fontWeight: 700, fontSize: 15, color: "var(--text-primary)" }}>{k.name}</div>
                  <span style={{ fontSize: 9, fontFamily: "JetBrains Mono", fontWeight: 700, color: cat.text, background: cat.bg, border: `1px solid ${cat.border}`, borderRadius: 4, padding: "2px 6px", letterSpacing: "0.06em", whiteSpace: "nowrap" }}>{cat.label}</span>
                </div>
                <div style={{ fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.6 }}>{k.description}</div>
                {k.params_hint && k.params_hint !== "None" && (
                  <div style={{ fontSize: 10, fontFamily: "JetBrains Mono", color: "var(--text-secondary)", background: "var(--bg)", borderRadius: 4, padding: "4px 8px", marginTop: 2 }}>⚙ {k.params_hint}</div>
                )}
                <div style={{ fontSize: 10, fontFamily: "JetBrains Mono", color: "var(--text-secondary)", marginTop: 2 }}>id: <span style={{ color: cat.text }}>{k.id}</span></div>
              </div>
            );
          })}
        </div>
      </Panel>


    </div>
  );
}

