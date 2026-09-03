import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { fmtNum, fmtPct, fmtRupee } from "@/lib/format";
import Panel from "@/components/Panel";
import StatTile from "@/components/StatTile";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, CartesianGrid
} from "recharts";
import { FlowArrow, TrendUp, TrendDown, Lightning, ChartBar, ArrowsClockwise, Flask } from "@phosphor-icons/react";

const CATEGORY_COLORS = {
  trend:     { bg: "rgba(59,130,246,0.10)", border: "#3b82f6", text: "#3b82f6", label: "TREND" },
  reversal:  { bg: "rgba(168,85,247,0.10)", border: "#a855f7", text: "#a855f7", label: "REVERSAL" },
  breakout:  { bg: "rgba(234,179,8,0.10)",  border: "#eab308", text: "#eab308", label: "BREAKOUT" },
  momentum:  { bg: "rgba(239,68,68,0.10)",  border: "#ef4444", text: "#ef4444", label: "MOMENTUM" },
  scalping:  { bg: "rgba(20,184,166,0.10)", border: "#14b8a6", text: "#14b8a6", label: "SCALPING" },
};

function StrategyCard({ k, selected, onClick }) {
  const cat = CATEGORY_COLORS[k.category] || CATEGORY_COLORS.trend;
  return (
    <div
      onClick={onClick}
      style={{
        background: selected ? cat.bg : "var(--surface)",
        border: `1.5px solid ${selected ? cat.border : "var(--border)"}`,
        borderRadius: 12,
        padding: "16px 18px",
        cursor: "pointer",
        transition: "all 0.18s ease",
        boxShadow: selected ? `0 0 0 2px ${cat.border}33` : "none",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
        <div style={{ fontFamily: "Outfit", fontWeight: 700, fontSize: 14, color: "var(--text-primary)" }}>{k.name}</div>
        <span style={{ fontSize: 9, fontFamily: "JetBrains Mono", fontWeight: 700, color: cat.text, background: cat.bg, border: `1px solid ${cat.border}`, borderRadius: 4, padding: "2px 6px", letterSpacing: "0.06em" }}>{cat.label}</span>
      </div>
      <div style={{ fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.5, marginBottom: 10 }}>{k.description}</div>
      {k.params_hint && k.params_hint !== "None" && (
        <div style={{ fontSize: 10, fontFamily: "JetBrains Mono", color: "var(--text-secondary)", background: "var(--bg)", borderRadius: 4, padding: "4px 8px" }}>⚙ {k.params_hint}</div>
      )}
    </div>
  );
}

function MetricBadge({ label, value, positive, neutral }) {
  const color = neutral ? "var(--text-primary)" : positive ? "var(--buy)" : "var(--sell)";
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, padding: "14px 18px", minWidth: 110 }}>
      <div style={{ fontSize: 10, fontFamily: "JetBrains Mono", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 800, fontFamily: "Outfit", color }}>{value}</div>
    </div>
  );
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 14px", fontSize: 11, fontFamily: "JetBrains Mono", color: "var(--text-primary)", boxShadow: "0 4px 20px rgba(0,0,0,0.3)" }}>
      <div style={{ color: "var(--text-secondary)", marginBottom: 4 }}>{String(d.ts || d.t).slice(0, 16)}</div>
      <div>Equity: <span style={{ color: "#00E676", fontWeight: 700 }}>{fmtRupee(d.equity)}</span></div>
      <div>Price: <span style={{ color: "var(--text-primary)" }}>{fmtRupee(d.price)}</span></div>
    </div>
  );
};

export default function Backtest() {
  const [kinds, setKinds]     = useState([]);
  const [symbols, setSymbols] = useState(["RELIANCE"]);
  const [form, setForm]       = useState({ strategy_kind: "ema_crossover", symbol: "RELIANCE", period_days: 30 });
  const [result, setResult]   = useState(null);
  const [history, setHistory] = useState([]);
  const [busy, setBusy]       = useState(false);
  const [sectorResult, setSectorResult] = useState(null);
  const [sectorBusy, setSectorBusy] = useState(false);
  const [activeTab, setActiveTab] = useState("curve"); // curve | trades | sector

  useEffect(() => {
    api.get("/strategies/kinds").then(({ data }) => setKinds(data.kinds));
    api.get("/market/symbols").then(({ data }) => setSymbols(data.symbols));
    api.get("/backtest/history").then(({ data }) => setHistory(data.runs));
  }, []);

  const run = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/backtest/run", { ...form, params: {} });
      setResult(data);
      setActiveTab("curve");
      const { data: h } = await api.get("/backtest/history");
      setHistory(h.runs);
      toast.success("Backtest complete!");
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  const runSectorAnalysis = async () => {
    setSectorBusy(true);
    try {
      const { data } = await api.post("/backtest/sector-accuracy", { ...form, params: {} });
      setSectorResult(data);
      setActiveTab("sector");
      toast.success("Sector analysis complete!");
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed sector analysis"); }
    finally { setSectorBusy(false); }
  };

  const loadHistoryRun = async (id) => {
    setBusy(true);
    try {
      const { data } = await api.get(`/backtest/run/${id}`);
      setResult(data);
      setForm({
        ...form,
        strategy_kind: data.strategy_kind,
        symbol: data.symbol,
        period_days: data.period_days,
      });
      setSectorResult(null);
      setActiveTab("curve");
      window.scrollTo({ top: 0, behavior: "smooth" });
      toast.success("Loaded history run");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load run");
    } finally {
      setBusy(false);
    }
  };

  const deleteRun = async (e, id) => {
    e.stopPropagation();
    try {
      await api.delete(`/backtest/run/${id}`);
      setHistory(history.filter(h => h.id !== id));
      toast.success("Run deleted!");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to delete");
    }
  };

  const selectedKind = kinds.find(k => k.id === form.strategy_kind);
  const m = result?.metrics || {};
  const trades = result?.trades_log || [];
  const bestTrade = trades.length ? Math.max(...trades.map(t => t.pnl)) : 0;
  const worstTrade = trades.length ? Math.min(...trades.map(t => t.pnl)) : 0;

  return (
    <div className="space-y-5" data-testid="backtest-page">
      <div>
        <h1 style={{ fontFamily: "Outfit", fontWeight: 900, fontSize: 28, letterSpacing: "-0.02em", display: "flex", alignItems: "center", gap: "8px" }}><Flask weight="duotone" color="var(--brand)" size={32} />Backtest Lab</h1>
        <p className="dim text-sm mt-1">Test any strategy on real historical data before using real money. Like a time machine for trading.</p>
      </div>

      {/* Configure & Run */}
      <Panel title="Configure & Run" kicker={selectedKind ? selectedKind.name : "Select a strategy below"}>
        <div style={{ padding: "16px", display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: 12 }}>
          <div>
            <label style={{ display: "block", fontSize: 10, fontFamily: "JetBrains Mono", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>Symbol</label>
            <select className="terminal" value={form.symbol} data-testid="bt-symbol"
              onChange={e => setForm({ ...form, symbol: e.target.value })}>
              {symbols.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label style={{ display: "block", fontSize: 10, fontFamily: "JetBrains Mono", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>Days to Test</label>
            <input className="terminal" type="number" min="1" max="365" value={form.period_days}
              data-testid="bt-period"
              onChange={e => setForm({ ...form, period_days: parseInt(e.target.value) })} />
          </div>
          <div>
            <label style={{ display: "block", fontSize: 10, fontFamily: "JetBrains Mono", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>Strategy</label>
            <select className="terminal" value={form.strategy_kind} data-testid="bt-kind"
              onChange={e => setForm({ ...form, strategy_kind: e.target.value })}>
              {kinds.map(k => <option key={k.id} value={k.id}>{k.name}</option>)}
            </select>
          </div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 12 }}>
            <button className="btn btn-primary" disabled={busy} onClick={run} data-testid="bt-run-btn"
              style={{ whiteSpace: "nowrap", gap: 8, display: "flex", alignItems: "center" }}>
              {busy ? <ArrowsClockwise size={14} weight="bold" className="animate-spin" /> : <FlowArrow size={14} weight="bold" />}
              {busy ? "Running…" : "Run Backtest"}
            </button>
            <button className="btn" disabled={sectorBusy} onClick={runSectorAnalysis} data-testid="bt-sector-btn"
              style={{ whiteSpace: "nowrap", gap: 8, display: "flex", alignItems: "center", background: "var(--surface)", border: "1px solid var(--border)" }}>
              {sectorBusy ? <ArrowsClockwise size={14} weight="bold" className="animate-spin" /> : <ChartBar size={14} weight="bold" />}
              {sectorBusy ? "Analyzing…" : "Sector Matrix"}
            </button>
            {(result || sectorResult) && (
              <button className="btn" onClick={() => { setResult(null); setSectorResult(null); }} title="Clear results and go back to normal"
                style={{ whiteSpace: "nowrap", gap: 8, display: "flex", alignItems: "center", background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
                <ArrowsClockwise size={14} weight="bold" />
                Reset
              </button>
            )}
          </div>
        </div>
      </Panel>

      {/* Results */}
      {(result || sectorResult) && (
        <>
          {/* Metrics Strip */}
          {result && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
              <MetricBadge label={`Total Return · ${result.data_source}`} value={fmtPct(m.total_return_pct)} positive={m.total_return_pct >= 0} />
              <MetricBadge label="Win Rate" value={fmtPct(m.win_rate_pct)} positive={m.win_rate_pct >= 50} />
              <MetricBadge label="Max Drawdown" value={fmtPct(-m.max_drawdown_pct)} positive={false} />
              <MetricBadge label="Sharpe Ratio" value={fmtNum(m.sharpe)} positive={m.sharpe >= 1} />
              <MetricBadge label="Final Equity" value={fmtRupee(m.final_equity)} neutral />
              <MetricBadge label="Total Trades" value={m.trades} neutral />
              <MetricBadge label="Best Trade" value={fmtRupee(bestTrade)} positive />
              <MetricBadge label="Worst Trade" value={fmtRupee(worstTrade)} positive={false} />
            </div>
          )}

          {/* Tabs */}
          <Panel title="Backtest Results">
            <div style={{ borderBottom: "1px solid var(--border)", display: "flex", gap: 24, padding: "0 16px" }}>
              {result && (
                <>
                  <div onClick={() => setActiveTab("curve")} className={`cursor-pointer py-3 text-sm font-bold ${activeTab === "curve" ? "text-[var(--text-primary)]" : "text-[var(--text-secondary)]"}`} style={{ borderBottom: activeTab === "curve" ? "2px solid var(--brand)" : "2px solid transparent" }}>
                    Equity Curve
                  </div>
                  <div onClick={() => setActiveTab("trades")} className={`cursor-pointer py-3 text-sm font-bold ${activeTab === "trades" ? "text-[var(--text-primary)]" : "text-[var(--text-secondary)]"}`} style={{ borderBottom: activeTab === "trades" ? "2px solid var(--brand)" : "2px solid transparent" }}>
                    Trade Log
                  </div>
                </>
              )}
              {sectorResult && (
                <div onClick={() => setActiveTab("sector")} className={`cursor-pointer py-3 text-sm font-bold ${activeTab === "sector" ? "text-[var(--text-primary)]" : "text-[var(--text-secondary)]"}`} style={{ borderBottom: activeTab === "sector" ? "2px solid var(--brand)" : "2px solid transparent" }}>
                  Sector Matrix
                </div>
              )}
            </div>

            {result && activeTab === "curve" && (
              <div style={{ height: 300, padding: "16px 0" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={result.equity_curve} margin={{ top: 10, right: 24, bottom: 0, left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="t" tick={{ fill: "#555", fontSize: 9, fontFamily: "JetBrains Mono" }} stroke="#333" />
                    <YAxis domain={["auto", "auto"]} tick={{ fill: "#555", fontSize: 9, fontFamily: "JetBrains Mono" }} stroke="#333" />
                    <ReferenceLine y={100000} stroke="#444" strokeDasharray="4 4" label={{ value: "Start ₹1L", fill: "#666", fontSize: 9 }} />
                    <Tooltip content={<CustomTooltip />} />
                    <Line type="linear" dataKey="equity"
                      stroke={m.total_return_pct >= 0 ? "#00E676" : "#ef4444"}
                      strokeWidth={2} dot={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {result && activeTab === "trades" && (
              <div style={{ overflowX: "auto" }}>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="dim text-[10px] uppercase tracking-widest border-b border-[#222]">
                      <th className="text-left py-2 px-4">#</th>
                      <th className="text-left py-2 px-4">Side</th>
                      <th className="text-right py-2 px-4">Entry ₹</th>
                      <th className="text-right py-2 px-4">Exit ₹</th>
                      <th className="text-right py-2 px-4">Qty</th>
                      <th className="text-right py-2 px-4">P&L ₹</th>
                      <th className="text-left py-2 px-4">Time</th>
                    </tr>
                  </thead>
                  <tbody className="cell-divider">
                    {trades.map((t, i) => (
                      <tr key={i}>
                        <td className="py-2 px-4 dim mono">{i + 1}</td>
                        <td className={`py-2 px-4 mono font-bold ${t.side === "BUY" ? "buy" : "sell"}`}>{t.side}</td>
                        <td className="py-2 px-4 text-right num">{fmtRupee(t.entry)}</td>
                        <td className="py-2 px-4 text-right num">{fmtRupee(t.exit)}</td>
                        <td className="py-2 px-4 text-right num dim">{t.qty}</td>
                        <td className={`py-2 px-4 text-right num font-bold ${t.pnl >= 0 ? "buy" : "sell"}`}>{t.pnl >= 0 ? "+" : ""}{fmtRupee(t.pnl)}</td>
                        <td className="py-2 px-4 mono dim" style={{ fontSize: 10 }}>{String(t.ts || "").slice(0, 16)}</td>
                      </tr>
                    ))}
                    {trades.length === 0 && (
                      <tr><td colSpan={7} className="p-8 text-center dim text-xs">No trades generated. Try a longer period or different symbol.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {activeTab === "sector" && sectorResult && (
              <div style={{ overflowX: "auto", padding: "16px" }}>
                <div style={{ marginBottom: "16px", fontWeight: "bold", fontSize: "14px", color: "var(--text-primary)" }}>
                  Strategy: <span style={{ color: "var(--brand)" }}>{kinds.find(k => k.id === sectorResult.strategy_kind)?.name || sectorResult.strategy_kind}</span>
                </div>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="dim text-[10px] uppercase tracking-widest border-b border-[#222]">
                      <th className="text-left py-2 px-4">Sector</th>
                      <th className="text-right py-2 px-4">Accuracy (Win %)</th>
                      <th className="text-left py-2 px-4">Performance Indicator</th>
                      <th className="text-left py-2 px-4">Stocks Used</th>
                    </tr>
                  </thead>
                  <tbody className="cell-divider">
                    {Object.entries(sectorResult.sector_accuracy).map(([sector, data]) => {
                      const winRate = typeof data === "number" ? data : data.win_rate;
                      const symbols = typeof data === "number" ? [] : data.symbols;
                      const isGood = winRate >= 0.5;
                      const displayPct = `${fmtNum(winRate * 100, 2)}%`;
                      return (
                        <tr key={sector}>
                          <td className="py-2 px-4 mono font-bold text-[14px]">{sector}</td>
                          <td className="py-2 px-4 text-right num text-[16px] font-bold">
                            {displayPct}
                          </td>
                          <td className="py-2 px-4">
                            <div style={{ width: "100%", maxWidth: "200px", height: "8px", background: "var(--bg)", borderRadius: "4px", overflow: "hidden" }}>
                              <div style={{ width: `${Math.min(winRate * 100, 100)}%`, height: "100%", background: isGood ? "var(--buy)" : "var(--sell)", transition: "width 0.5s ease" }} />
                            </div>
                          </td>
                          <td className="py-2 px-4 text-[10px] dim">
                            {symbols.join(", ")}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                <p className="dim text-xs mt-4 text-center">Accuracy is calculated across all major stocks in the sector over {form.period_days} days.</p>
              </div>
            )}
          </Panel>
        </>
      )}

      {/* History */}
      <Panel title="Backtest History" kicker={`${history.length} runs`}>
        <div style={{ overflowX: "auto" }}>
          <table className="w-full text-xs">
            <thead>
              <tr className="dim text-[10px] uppercase tracking-widest border-b border-[#222]">
                <th className="text-left py-2 px-4">Strategy</th>
                <th className="text-left py-2 px-4">Symbol</th>
                <th className="text-right py-2 px-4">Period</th>
                <th className="text-right py-2 px-4">Return %</th>
                <th className="text-right py-2 px-4">Sharpe</th>
                <th className="text-right py-2 px-4">Max DD</th>
                <th className="text-right py-2 px-4">Win %</th>
                <th className="text-right py-2 px-4">Trades</th>
                <th className="text-center py-2 px-4">Actions</th>
              </tr>
            </thead>
            <tbody className="cell-divider">
              {history.map(h => (
                <tr 
                  key={h.id} 
                  data-testid={`bt-history-${h.id}`}
                  onClick={() => loadHistoryRun(h.id)}
                  style={{ cursor: "pointer" }}
                  className="hover-bg"
                >
                  <td className="py-2 px-4 mono">{h.strategy_kind}</td>
                  <td className="py-2 px-4 mono">{h.symbol}</td>
                  <td className="py-2 px-4 text-right num dim">{h.period_days}d</td>
                  <td className={`py-2 px-4 text-right num ${(h.metrics?.total_return_pct || 0) >= 0 ? "buy" : "sell"}`}>{fmtPct(h.metrics?.total_return_pct || 0)}</td>
                  <td className="py-2 px-4 text-right num">{fmtNum(h.metrics?.sharpe || 0)}</td>
                  <td className="py-2 px-4 text-right num sell">{fmtPct(-(h.metrics?.max_drawdown_pct || 0))}</td>
                  <td className="py-2 px-4 text-right num">{fmtPct(h.metrics?.win_rate_pct || 0)}</td>
                  <td className="py-2 px-4 text-right num dim">{h.metrics?.trades || 0}</td>
                  <td className="py-2 px-4 text-center">
                    <button 
                      onClick={(e) => deleteRun(e, h.id)}
                      className="text-red-500 hover:text-red-400 p-1 rounded hover:bg-[#333] transition-colors inline-block"
                      title="Delete Run"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                    </button>
                  </td>
                </tr>
              ))}
              {history.length === 0 && <tr><td colSpan={9} className="p-8 text-center dim text-xs">No runs yet. Run your first backtest above!</td></tr>}
            </tbody>
          </table>
        </div>
      </Panel>

      {/* Strategy Picker / Library */}
      <Panel title="Available Strategy Library" kicker={`${kinds.length} available`}>
        <div style={{ padding: "16px", display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
          {kinds.map(k => (
            <StrategyCard
              key={k.id}
              k={k}
              selected={form.strategy_kind === k.id}
              onClick={() => {
                setForm({ ...form, strategy_kind: k.id });
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
            />
          ))}
        </div>
      </Panel>
    </div>
  );
}
