import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { fmtDateTime, fmtTime, fmtInt, fmtNum } from "@/lib/format";
import Panel from "@/components/Panel";
import { Plus } from "@phosphor-icons/react";

export default function Orders() {
  const [orders, setOrders] = useState([]);
  const [snap, setSnap] = useState([]);
  const [brokers, setBrokers] = useState(["mock"]);
  const [tab, setTab] = useState("real");
  const [form, setForm] = useState({ broker: "aliceblue", symbol: "RELIANCE", side: "BUY", qty: 1, price: 0, order_type: "MARKET", product: "MIS" });

  const load = async () => {
    const [a, b, c] = await Promise.all([
      api.get("/orders?limit=200"),
      api.get("/market/snapshot"),
      api.get("/brokers"),
    ]);
    setOrders(a.data.orders); setSnap(b.data.ticks);
    setBrokers(c.data.available);
  };

  useEffect(() => {
    load();
    const i = setInterval(load, 10000);
    
    // Instantly refresh when orders are placed via QuickOrderPanel
    const handleOrder = () => load();
    window.addEventListener('orderPlaced', handleOrder);
    
    return () => {
      clearInterval(i);
      window.removeEventListener('orderPlaced', handleOrder);
    };
  }, []);
  useEffect(() => {
    // auto-fill price from snapshot
    const t = snap.find((x) => x.symbol === form.symbol);
    if (t) setForm((f) => f.price ? f : { ...f, price: t.ltp });
  }, [snap, form.symbol]);

  const submit = async (e) => {
    e.preventDefault();
    try {
      const t = snap.find((x) => x.symbol === form.symbol);
      const payload = { ...form, price: form.price || t?.ltp || 0, qty: parseInt(form.qty), broker: form.broker };
      await api.post("/orders", payload);
      toast.success("Order placed");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Order failed"); }
  };

  const displayedOrders = orders.filter(o => tab === "real" ? !o.is_mock : o.is_mock);

  return (
    <div className="space-y-4" data-testid="orders-page">
      <div>
        <h1 style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 28, letterSpacing: "-0.02em" }}>Trade book.</h1>
        <p className="dim text-sm mt-1">Manual order pad + full execution history routed directly to AliceBlue live servers.</p>
      </div>

      <Panel title="Place order" kicker="manual">
        <form className="p-4 grid grid-cols-2 md:grid-cols-6 gap-3" onSubmit={submit}>
          <div className="hidden">
            <input type="hidden" value="aliceblue" />
          </div>
          <div>
            <label className="block dim text-[10px] mono uppercase tracking-widest mb-1">Symbol</label>
            <select className="terminal" value={form.symbol} data-testid="order-symbol-select" onChange={(e) => setForm({ ...form, symbol: e.target.value, price: 0 })}>
              {snap.map((t) => <option key={t.symbol} value={t.symbol}>{t.symbol}</option>)}
            </select>
          </div>
          <div>
            <label className="block dim text-[10px] mono uppercase tracking-widest mb-1">Side</label>
            <select className="terminal" value={form.side} data-testid="order-side-select" onChange={(e) => setForm({ ...form, side: e.target.value })}>
              <option>BUY</option><option>SELL</option>
            </select>
          </div>
          <div>
            <label className="block dim text-[10px] mono uppercase tracking-widest mb-1">Qty</label>
            <input className="terminal" type="number" min="1" value={form.qty} data-testid="order-qty-input" onChange={(e) => setForm({ ...form, qty: e.target.value })} />
          </div>
          <div>
            <label className="block dim text-[10px] mono uppercase tracking-widest mb-1">Price</label>
            <input className="terminal" type="number" step="0.01" value={form.price} data-testid="order-price-input" onChange={(e) => setForm({ ...form, price: parseFloat(e.target.value) })} />
          </div>
          <div className="flex items-end">
            <button className={`w-full py-2.5 px-4 rounded text-xs font-bold tracking-wider transition-colors flex items-center justify-center gap-1 ${form.side === "BUY" ? "bg-[#14532d] hover:bg-[#166534] text-white" : "bg-red-800 hover:bg-red-700 text-white"}`} data-testid="order-submit-btn" type="submit" style={{ height: '43px' }}>
              <Plus size={14} weight="bold" /> {form.side} {form.symbol}
            </button>
          </div>
        </form>
      </Panel>

      <Panel title="Executions" kicker={`${displayedOrders.length} orders`}>
        <div className="flex border-b border-gray-200">
          <button 
            className={`flex-1 py-2.5 text-xs font-bold tracking-wider transition-colors ${tab === 'real' ? 'border-b-2 border-[#14532d] text-[#14532d] bg-green-50/30' : 'text-gray-500 hover:text-gray-900 hover:bg-gray-50'}`} 
            onClick={() => setTab('real')}
          >
            REAL TRADES
          </button>
          <button 
            className={`flex-1 py-2.5 text-xs font-bold tracking-wider transition-colors border-l border-gray-100 ${tab === 'mock' ? 'border-b-2 border-orange-500 text-orange-600 bg-orange-50/30' : 'text-gray-500 hover:text-gray-900 hover:bg-gray-50'}`} 
            onClick={() => setTab('mock')}
          >
            PAPER TRADES (MOCK)
          </button>
        </div>
        <div className="w-full overflow-hidden">
          <table className="w-full text-xs">
          <thead><tr className="dim text-[10px] uppercase tracking-widest border-b border-[#222]">
            <th className="text-left py-2 px-2">Time</th>
            <th className="text-left py-2 px-2">Symbol</th>
            <th className="text-left py-2 px-2">Side</th>
            <th className="text-right py-2 px-2">Qty</th>
            <th className="text-right py-2 px-2">Price</th>
            <th className="text-left py-2 px-2">Broker</th>
            <th className="text-left py-2 px-2">Source</th>
            <th className="text-left py-2 px-2">Status</th>
          </tr></thead>
          <tbody className="cell-divider">
            {displayedOrders.map((o) => (
              <tr key={o.id} data-testid={`order-row-${o.id}`}>
                <td className="py-2 px-2 mono dim whitespace-nowrap" title={fmtDateTime(o.placed_at)}>{fmtTime(o.placed_at)}</td>
                <td className="py-2 px-2 mono">{o.symbol}</td>
                <td className={`py-2 px-2 mono ${o.side === "BUY" ? "buy" : "sell"}`}>{o.side}</td>
                <td className="py-2 px-2 text-right num">{fmtInt(o.qty)}</td>
                <td className="py-2 px-2 text-right num">{fmtNum(o.price)}</td>
                <td className="py-2 px-2 mono dim">{o.broker}</td>
                <td className="py-2 px-2 mono dim">
                  {o.source.startsWith("strategy:") ? (
                    <Link to="/strategies" className="text-blue-500 hover:underline" title="Click to view & manage this strategy">{o.source.replace("strategy:", "")}</Link>
                  ) : (
                    o.source
                  )}
                </td>
                <td className="py-2 px-2 align-middle" title={o.reject_reason || ""}>
  <div className="flex flex-col">
    <span className={`mono ${o.status === "FILLED" ? "buy" : o.status === "REJECTED" ? "sell" : ""}`}>{o.status}</span>
    {o.reject_reason && (
      <span className="text-[9px] text-red-500/80 truncate max-w-[120px] lg:max-w-[200px] font-sans dim mt-0.5 leading-none">
        {
        o.reject_reason
          .replace(/^(ORA|RED):/, '')
          .replace(/'MIS' Orders are disallowed after system square off/i, 'Market closed for Intraday (MIS)')
          .replace(/Margin Shortfall:INR ([0-9.]+) Available:INR ([0-9.]+) for .*/i, 'Margin Shortfall: ₹$1 (Available: ₹$2)')
          .trim()
      }
      </span>
    )}
  </div>
</td>
              </tr>
            ))}
            {orders.length === 0 && <tr><td colSpan={8} className="p-8 text-center dim text-xs">No orders yet.</td></tr>}
          </tbody>
        </table>
        </div>
      </Panel>
    </div>
  );
}
