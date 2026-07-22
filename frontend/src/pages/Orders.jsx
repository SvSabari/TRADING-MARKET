import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { fmtDateTime, fmtInt, fmtNum } from "@/lib/format";
import Panel from "@/components/Panel";
import { Plus } from "@phosphor-icons/react";

export default function Orders() {
  const [orders, setOrders] = useState([]);
  const [snap, setSnap] = useState([]);
  const [brokers, setBrokers] = useState(["mock"]);
  const [form, setForm] = useState({ broker: "mock", symbol: "RELIANCE", side: "BUY", qty: 1, price: 0, order_type: "MARKET", product: "MIS" });

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
    const i = setInterval(load, 3000);
    return () => clearInterval(i);
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

  return (
    <div className="space-y-4" data-testid="orders-page">
      <div>
        <h1 style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 28, letterSpacing: "-0.02em" }}>Trade book.</h1>
        <p className="dim text-sm mt-1">Manual order pad + full execution history routed through the mock broker.</p>
      </div>

      <Panel title="Place order" kicker="manual">
        <form className="p-4 grid grid-cols-2 md:grid-cols-6 gap-3" onSubmit={submit}>
          <div>
            <label className="block dim text-[10px] mono uppercase tracking-widest mb-1">Broker</label>
            <select className="terminal" value={form.broker} data-testid="order-broker-select" onChange={(e) => setForm({ ...form, broker: e.target.value })}>
              {brokers.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
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
          <button className={`btn justify-center ${form.side === "BUY" ? "btn-primary" : "btn-danger"}`} data-testid="order-submit-btn" type="submit">
            <Plus size={14} weight="bold" /> {form.side} {form.symbol}
          </button>
        </form>
      </Panel>

      <Panel title="Executions" kicker={`${orders.length} orders`}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[700px] text-xs">
          <thead><tr className="dim text-[10px] uppercase tracking-widest border-b border-[#222]">
            <th className="text-left py-2 px-4">Time</th>
            <th className="text-left py-2 px-4">Symbol</th>
            <th className="text-left py-2 px-4">Side</th>
            <th className="text-right py-2 px-4">Qty</th>
            <th className="text-right py-2 px-4">Price</th>
            <th className="text-left py-2 px-4">Broker</th>
            <th className="text-left py-2 px-4">Source</th>
            <th className="text-left py-2 px-4">Status</th>
          </tr></thead>
          <tbody className="cell-divider">
            {orders.map((o) => (
              <tr key={o.id} data-testid={`order-row-${o.id}`}>
                <td className="py-2 px-4 mono dim">{fmtDateTime(o.placed_at)}</td>
                <td className="py-2 px-4 mono">{o.symbol}</td>
                <td className={`py-2 px-4 mono ${o.side === "BUY" ? "buy" : "sell"}`}>{o.side}</td>
                <td className="py-2 px-4 text-right num">{fmtInt(o.qty)}</td>
                <td className="py-2 px-4 text-right num">{fmtNum(o.price)}</td>
                <td className="py-2 px-4 mono dim">{o.broker}</td>
                <td className="py-2 px-4 mono dim">
                  {o.source.startsWith("strategy:") ? (
                    <Link to="/strategies" className="text-blue-500 hover:underline" title="Click to view & manage this strategy">{o.source}</Link>
                  ) : (
                    o.source
                  )}
                </td>
                <td className={`py-2 px-4 mono ${o.status === "FILLED" ? "buy" : ""}`}>{o.status}</td>
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
