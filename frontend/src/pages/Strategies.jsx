import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import Panel from "@/components/Panel";
import { Plus, Trash } from "@phosphor-icons/react";

export default function Strategies() {
  const [kinds, setKinds] = useState([]);
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ name: "", kind: "ema_crossover", symbols: "" });
  const [symbolsList, setSymbolsList] = useState([]);
  const [showSymbolDropdown, setShowSymbolDropdown] = useState(false);

  const load = async () => {
    const [a, b, c] = await Promise.all([api.get("/strategies/kinds"), api.get("/strategies"), api.get("/market/snapshot").catch(() => ({ data: { ticks: [] } }))]);
    setKinds(a.data.kinds); setItems(b.data.strategies);
    if (c.data && c.data.ticks) setSymbolsList(c.data.ticks.map(t => t.symbol));
  };
  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    if (!form.name) return toast.error("Name required");
    try {
      await api.post("/strategies", {
        name: form.name, kind: form.kind, enabled: false,
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
        <h1 style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 28, letterSpacing: "-0.02em" }}>Strategy manager.</h1>
        <p className="dim text-sm mt-1">Enable, configure and combine algorithmic strategies. Mock execution only.</p>
      </div>
      <Panel title="Available kinds" kicker="library">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-[#222]">
          {kinds.map((k) => (
            <div key={k.id} className="bg-[#121212] p-4">
              <div style={{ fontFamily: "Chivo", fontWeight: 700, fontSize: 14 }}>{k.name}</div>
              <div className="mono text-[10px] dim uppercase tracking-widest">{k.id}</div>
              <div className="text-xs dim mt-2">{k.description}</div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Create strategy" kicker={scheduler ? `scheduler · ${scheduler.fires} fires` : "scheduler offline"}>
        <div className="p-4 grid grid-cols-2 md:grid-cols-6 gap-3">
          <input className="terminal md:col-span-2" data-testid="strategy-name-input" placeholder="Nickname (e.g. Apple Rule)" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <select className="terminal" data-testid="strategy-kind-select" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
            {kinds.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
          </select>
          <div className="relative">
            <div 
              className="terminal cursor-pointer min-h-[38px] flex items-center overflow-hidden whitespace-nowrap" 
              onClick={() => setShowSymbolDropdown(!showSymbolDropdown)}
            >
              {form.symbols || <span className="dim">Which Stock? (Click)</span>}
            </div>
            {showSymbolDropdown && (
              <div className="absolute top-full left-0 w-64 max-h-64 overflow-y-auto bg-[#121212] border border-[#333] z-50 p-2 shadow-xl">
                <div className="text-xs mb-2 dim flex justify-between">
                  <span>Select Stocks:</span>
                  <button onClick={(e) => { e.stopPropagation(); setShowSymbolDropdown(false); }} className="hover:text-white">Close</button>
                </div>
                {symbolsList.map(sym => {
                  const isSelected = form.symbols.split(",").map(s => s.trim()).includes(sym);
                  return (
                    <label key={sym} className="flex items-center px-2 py-1 hover:bg-[#222] cursor-pointer text-sm">
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
          <input className="terminal" type="number" min="5" placeholder="Check Every (Seconds)" value={form.interval_seconds} data-testid="strategy-interval-input" onChange={(e) => setForm({ ...form, interval_seconds: e.target.value })} />
          <input className="terminal" type="number" min="1" placeholder="How Many to Buy?" value={form.qty} data-testid="strategy-qty-input" onChange={(e) => setForm({ ...form, qty: e.target.value })} />
          <button className="btn btn-primary md:col-span-6 justify-center" data-testid="strategy-create-btn" onClick={create}><Plus size={14} weight="bold" /> Create</button>
        </div>
      </Panel>

      <Panel title="My strategies" kicker={`${items.length} instances`}>
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
    </div>
  );
}
