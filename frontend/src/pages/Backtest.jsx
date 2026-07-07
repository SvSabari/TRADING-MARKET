import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { fmtNum, fmtPct, fmtRupee } from "@/lib/format";
import Panel from "@/components/Panel";
import StatTile from "@/components/StatTile";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip } from "recharts";
import { FlowArrow } from "@phosphor-icons/react";

export default function Backtest() {
  const [kinds, setKinds] = useState([]);
  const [symbols, setSymbols] = useState(["RELIANCE"]);
  const [form, setForm] = useState({ strategy_kind: "ema_crossover", symbol: "RELIANCE", period_days: 30 });
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.get("/strategies/kinds").then(({ data }) => setKinds(data.kinds));
    api.get("/market/symbols").then(({ data }) => setSymbols(data.nifty50));
    api.get("/backtest/history").then(({ data }) => setHistory(data.runs));
  }, []);

  const run = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/backtest/run", { ...form, params: {} });
      setResult(data);
      const { data: h } = await api.get("/backtest/history");
      setHistory(h.runs);
      toast.success("Backtest complete");
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  return (
    <div className="space-y-4" data-testid="backtest-page">
      <div>
        <h1 style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 28, letterSpacing: "-0.02em" }}>Backtest lab.</h1>
        <p className="dim text-sm mt-1">Reads captured Parquet OHLCV (5-second buckets resampled to 1-minute) for the selected symbol. Falls back to synthetic walk-forward when no parquet data is present yet.</p>
      </div>

      <Panel title="Configure run" kicker="strategy · symbol · period">
        <div className="p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          <select className="terminal" value={form.strategy_kind} data-testid="bt-kind" onChange={(e) => setForm({ ...form, strategy_kind: e.target.value })}>
            {kinds.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
          </select>
          <select className="terminal" value={form.symbol} data-testid="bt-symbol" onChange={(e) => setForm({ ...form, symbol: e.target.value })}>
            {symbols.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <input className="terminal" type="number" min="5" max="365" value={form.period_days} data-testid="bt-period" onChange={(e) => setForm({ ...form, period_days: parseInt(e.target.value) })} />
          <button className="btn btn-primary justify-center" disabled={busy} onClick={run} data-testid="bt-run-btn">
            <FlowArrow size={14} weight="bold" /> {busy ? "Running…" : "Run backtest"}
          </button>
        </div>
      </Panel>

      {result && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-px bg-[#222]">
            <StatTile label={`Total return · ${result.data_source || "?"}`} value={fmtPct(result.metrics.total_return_pct)} accent={result.metrics.total_return_pct >= 0 ? "buy" : "sell"} big testid="bt-total-return" />
            <StatTile label="Win rate" value={fmtPct(result.metrics.win_rate_pct)} testid="bt-win-rate" />
            <StatTile label="Max DD" value={fmtPct(-result.metrics.max_drawdown_pct)} accent="sell" testid="bt-max-dd" />
            <StatTile label="Sharpe" value={fmtNum(result.metrics.sharpe)} accent={result.metrics.sharpe >= 1 ? "buy" : "sell"} testid="bt-sharpe" />
            <StatTile label="Final equity" value={fmtRupee(result.metrics.final_equity)} testid="bt-final" />
          </div>
          <Panel title="Equity curve" kicker={`${result.metrics.trades} trades`}>
            <div style={{ height: 280 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={result.equity_curve} margin={{ top: 10, right: 16, bottom: 0, left: 0 }}>
                  <XAxis dataKey="t" tick={{ fill: "#555", fontSize: 9, fontFamily: "JetBrains Mono" }} stroke="#222" />
                  <YAxis tick={{ fill: "#555", fontSize: 9, fontFamily: "JetBrains Mono" }} stroke="#222" />
                  <Tooltip contentStyle={{ background: "#0A0A0A", border: "1px solid #222", fontFamily: "JetBrains Mono", fontSize: 11 }} />
                  <Line type="monotone" dataKey="equity" stroke="#00E676" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Panel>
        </>
      )}

      <Panel title="Backtest history" kicker={`${history.length} runs`}>
        <table className="w-full text-xs">
          <thead><tr className="dim text-[10px] uppercase tracking-widest border-b border-[#222]">
            <th className="text-left py-2 px-4">Strategy</th>
            <th className="text-left py-2 px-4">Symbol</th>
            <th className="text-right py-2 px-4">Period</th>
            <th className="text-right py-2 px-4">Return %</th>
            <th className="text-right py-2 px-4">Sharpe</th>
            <th className="text-right py-2 px-4">Max DD</th>
            <th className="text-right py-2 px-4">Win %</th>
          </tr></thead>
          <tbody className="cell-divider">
            {history.map((h) => (
              <tr key={h.id} data-testid={`bt-history-${h.id}`}>
                <td className="py-2 px-4 mono">{h.strategy_kind}</td>
                <td className="py-2 px-4 mono">{h.symbol}</td>
                <td className="py-2 px-4 text-right num dim">{h.period_days}d</td>
                <td className={`py-2 px-4 text-right num ${h.metrics?.total_return_pct >= 0 ? "buy" : "sell"}`}>{fmtPct(h.metrics?.total_return_pct || 0)}</td>
                <td className="py-2 px-4 text-right num">{fmtNum(h.metrics?.sharpe || 0)}</td>
                <td className="py-2 px-4 text-right num sell">{fmtPct(-(h.metrics?.max_drawdown_pct || 0))}</td>
                <td className="py-2 px-4 text-right num">{fmtPct(h.metrics?.win_rate_pct || 0)}</td>
              </tr>
            ))}
            {history.length === 0 && <tr><td colSpan={7} className="p-8 text-center dim text-xs">No runs yet.</td></tr>}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
