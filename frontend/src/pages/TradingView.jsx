import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, API } from "@/lib/api";
import { fmtNum, fmtDateTime } from "@/lib/format";
import Panel from "@/components/Panel";
import { Copy, Lightning } from "@phosphor-icons/react";

export default function TradingView() {
  const [info, setInfo] = useState(null);
  const [signals, setSignals] = useState([]);
  const [form, setForm] = useState({ symbol: "RELIANCE", side: "BUY", price: 2890, qty: 10, strategy: "manual-test", alert_id: "" });

  const load = async () => {
    const [a, b] = await Promise.all([
      api.get("/tradingview/webhook-info"),
      api.get("/tradingview/signals"),
    ]);
    setInfo(a.data); setSignals(b.data.signals);
  };
  useEffect(() => {
    load();
    const i = setInterval(load, 3000);
    return () => clearInterval(i);
  }, []);

  const fire = async () => {
    try {
      const payload = { ...form, alert_id: form.alert_id || `manual-${Date.now()}` };
      const { data } = await api.post("/tradingview/test-fire", payload);
      if (data.duplicate) {
        toast.message("Duplicate alert — idempotency hit", { description: `Returned existing order ${data.order_id?.slice(0,8)}` });
      } else {
        toast.success(`Order ${data.order_id.slice(0, 8)} filled @ ₹${data.fill_price}`);
      }
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const fullUrl = info ? `${API.replace(/\/api$/, "")}${info.webhook_path}?secret=${info.secret}` : "";
  const examplePayload = info ? JSON.stringify(info.example_payload, null, 2) : "";

  return (
    <div className="space-y-4" data-testid="tradingview-page">
      <div>
        <h1 style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 28, letterSpacing: "-0.02em" }}>TradingView webhook.</h1>
        <p className="dim text-sm mt-1">Configure this URL in your TradingView alert message body. Each fire auto-executes a paper trade.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Your webhook URL" kicker={info?.per_user_secret ? "POST · JSON · per-user secret" : "POST · JSON"}>
          <div className="p-4 space-y-3">
            <div className="mono text-xs break-all bg-gray-100 p-3 border border-gray-200 text-gray-700" data-testid="webhook-url">{fullUrl}</div>
            <div className="flex gap-2">
              <button className="btn" data-testid="copy-webhook-btn" onClick={() => { navigator.clipboard.writeText(fullUrl); toast.success("Copied"); }}>
                <Copy size={14} weight="bold" /> Copy URL
              </button>
              <button className="btn btn-danger" data-testid="rotate-secret-btn" onClick={async () => {
                await api.post("/auth/webhook-secret/rotate");
                toast.success("Webhook secret rotated. Update your TradingView alerts.");
                load();
              }}>Rotate secret</button>
            </div>
            <div className="text-gray-500 text-[10px] mono uppercase tracking-widest mt-4">example payload</div>
            <pre className="bg-gray-100 p-3 border border-gray-200 text-xs overflow-x-auto text-gray-700" data-testid="example-payload">{examplePayload}</pre>
            <div className="text-gray-500 text-xs mt-2">
              In TradingView → Create Alert → Notifications → Webhook URL → paste the URL above. In the Message field paste the JSON.
              The <span className="mono">alert_id</span> field makes duplicate fires idempotent.
            </div>
          </div>
        </Panel>

        <Panel title="Test fire" kicker="simulate alert">
          <div className="p-4 grid grid-cols-2 gap-3">
            <div>
              <label className="block text-gray-500 text-[10px] mono uppercase tracking-widest mb-1">Symbol</label>
              <input className="terminal" data-testid="tv-test-symbol" value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })} />
            </div>
            <div>
              <label className="block text-gray-500 text-[10px] mono uppercase tracking-widest mb-1">Side</label>
              <select className="terminal" data-testid="tv-test-side" value={form.side} onChange={(e) => setForm({ ...form, side: e.target.value })}>
                <option>BUY</option><option>SELL</option>
              </select>
            </div>
            <div>
              <label className="block text-gray-500 text-[10px] mono uppercase tracking-widest mb-1">Price</label>
              <input className="terminal" type="number" step="0.01" data-testid="tv-test-price" value={form.price} onChange={(e) => setForm({ ...form, price: parseFloat(e.target.value) })} />
            </div>
            <div>
              <label className="block text-gray-500 text-[10px] mono uppercase tracking-widest mb-1">Qty</label>
              <input className="terminal" type="number" data-testid="tv-test-qty" value={form.qty} onChange={(e) => setForm({ ...form, qty: parseInt(e.target.value) })} />
            </div>
            <div className="col-span-2">
              <label className="block text-gray-500 text-[10px] mono uppercase tracking-widest mb-1">Strategy</label>
              <input className="terminal" data-testid="tv-test-strategy" value={form.strategy} onChange={(e) => setForm({ ...form, strategy: e.target.value })} />
            </div>
            <div className="col-span-2">
              <label className="block text-gray-500 text-[10px] mono uppercase tracking-widest mb-1">Alert ID (idempotency key — re-firing the same ID won&apos;t double-execute)</label>
              <input className="terminal" data-testid="tv-test-alert-id" value={form.alert_id} placeholder="auto-generated if empty" onChange={(e) => setForm({ ...form, alert_id: e.target.value })} />
            </div>
            <button className="btn btn-primary col-span-2 justify-center" data-testid="tv-test-fire-btn" onClick={fire}>
              <Lightning size={14} weight="bold" /> Fire test alert
            </button>
          </div>
        </Panel>
      </div>

      <Panel title="Signal history" kicker={`${signals.length} alerts`}>
        <table className="w-full text-xs">
          <thead><tr className="text-gray-500 text-[10px] uppercase tracking-widest border-b border-gray-200">
            <th className="text-left py-2 px-4">Received</th>
            <th className="text-left py-2 px-4">Symbol</th>
            <th className="text-left py-2 px-4">Side</th>
            <th className="text-right py-2 px-4">Price</th>
            <th className="text-right py-2 px-4">Qty</th>
            <th className="text-left py-2 px-4">Strategy</th>
            <th className="text-left py-2 px-4">Order ID</th>
          </tr></thead>
          <tbody className="cell-divider">
            {signals.map((s) => (
              <tr key={s.id} data-testid={`tv-signal-${s.id}`}>
                <td className="py-2 px-4 mono text-gray-500">{fmtDateTime(s.received_at)}</td>
                <td className="py-2 px-4 mono">{s.symbol}</td>
                <td className={`py-2 px-4 mono ${s.side === "BUY" ? "buy" : "sell"}`}>{s.side}</td>
                <td className="py-2 px-4 text-right num">{fmtNum(s.price)}</td>
                <td className="py-2 px-4 text-right num">{s.qty}</td>
                <td className="py-2 px-4 mono dim">{s.strategy}</td>
                <td className="py-2 px-4 mono dim">{s.order_id?.slice(0, 12) || "—"}</td>
              </tr>
            ))}
            {signals.length === 0 && <tr><td colSpan={7} className="p-8 text-center dim text-xs">No alerts received yet. Fire a test or wire up TradingView.</td></tr>}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
