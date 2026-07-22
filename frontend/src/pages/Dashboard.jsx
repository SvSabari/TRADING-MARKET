import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { usePolling } from "@/lib/use-polling";
import { api } from "@/lib/api";
import { fmtInt, fmtRupee } from "@/lib/format";
import Panel from "@/components/Panel";
import StatTile from "@/components/StatTile";
import LivePriceChart from "@/components/charts/LivePriceChart";
import MoversTable from "@/components/MoversTable";
import SignalsFeed from "@/components/SignalsFeed";

export default function Dashboard() {
  const { data: snap } = usePolling("/market/snapshot", { intervalMs: 2000 });
  const { data: pnl } = usePolling("/orders/pnl-summary", { intervalMs: 2000 });
  const { data: sig } = usePolling("/signals/live", { intervalMs: 2000 });
  const { data: parquet } = usePolling("/parquet/status", { intervalMs: 2000 });

  const [chartSym, setChartSym] = useState("RELIANCE");
  const [history, setHistory] = useState([]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const { data } = await api.get(`/market/history/${chartSym}?limit=120`);
        if (!cancelled) setHistory(data.candles);
      } catch (e) { console.error("history fetch failed:", e); }
    };
    load();
    const id = setInterval(load, 2000);
    return () => { cancelled = true; clearInterval(id); };
  }, [chartSym]);

  const ticks = snap?.ticks || [];
  const signals = sig?.signals || [];
  const gainers = [...ticks].sort((a, b) => b.change_pct - a.change_pct).slice(0, 6);
  const losers = [...ticks].sort((a, b) => a.change_pct - b.change_pct).slice(0, 6);

  return (
    <div className="space-y-4" data-testid="dashboard-page">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatTile label="Total P&L" value={fmtRupee(pnl?.total_pnl || 0)}
          accent={(pnl?.total_pnl || 0) >= 0 ? "buy" : "sell"} big testid="pnl-total" />
        <StatTile label="Unrealized" value={fmtRupee(pnl?.unrealized_pnl || 0)}
          accent={(pnl?.unrealized_pnl || 0) >= 0 ? "buy" : "sell"} testid="pnl-unrealized" />
        <StatTile label="Trades" value={fmtInt(pnl?.trades || 0)} testid="pnl-trades" />
        <StatTile label="Parquet rows" value={fmtInt(parquet?.rows_written || 0)} accent="buy" testid="parquet-rows" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Panel
          testid="chart-panel"
          title={`Live · ${chartSym}`}
          kicker={history.length ? `${history.length} ticks` : "loading"}
          right={
            <div className="flex gap-2">
              <select className="terminal !w-auto !py-1 !text-xs" value={["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "NIFTYNXT50"].includes(chartSym) ? "" : chartSym}
                onChange={(e) => setChartSym(e.target.value)} data-testid="chart-symbol-select">
                <option disabled value="">── Equities ──</option>
                {ticks.filter(t => !["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "NIFTYNXT50"].includes(t.symbol)).map((t) => (<option key={t.symbol} value={t.symbol}>{t.symbol}</option>))}
              </select>
              <select className="terminal !w-auto !py-1 !text-xs" value={["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "NIFTYNXT50"].includes(chartSym) ? chartSym : ""}
                onChange={(e) => setChartSym(e.target.value)} data-testid="chart-index-select">
                <option disabled value="">── Indices ──</option>
                {["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "NIFTYNXT50"].map((sym) => (<option key={sym} value={sym}>{sym}</option>))}
              </select>
            </div>
          }
          className="lg:col-span-2"
        >
          <LivePriceChart history={history} />
        </Panel>
        <SignalsFeed signals={signals} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <MoversTable rows={gainers} title="Top gainers" kicker="all symbols" accent="buy" testid="gainer" />
        <MoversTable rows={losers} title="Top losers" kicker="all symbols" accent="sell" testid="loser" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Panel testid="cta-tv" title="TradingView" kicker="webhook">
          <div className="p-4 space-y-3">
            <div className="dim text-xs">Forward your TradingView alerts to a single webhook URL. Each alert is auto-executed as a paper trade.</div>
            <Link to="/tradingview" className="btn btn-primary" data-testid="cta-tv-link">Configure webhook →</Link>
          </div>
        </Panel>
        <Panel testid="cta-parquet" title="Parquet capture" kicker="5-second buckets">
          <div className="p-4 space-y-3">
            <div className="num text-2xl">{fmtInt(parquet?.rows_written || 0)} <span className="dim text-xs">rows</span></div>
            <div className="dim text-xs">Per-symbol Parquet files at <span className="mono">{parquet?.parquet_dir}</span></div>
            <Link to="/parquet" className="btn" data-testid="cta-parquet-link">Open file browser →</Link>
          </div>
        </Panel>
        <Panel testid="cta-ai" title="AI assistant" kicker="Claude Sonnet 4.5">
          <div className="p-4 space-y-3">
            <div className="dim text-xs">Ask Claude to explain a signal, rank trades, or sanity-check a strategy idea.</div>
            <Link to="/ai" className="btn" data-testid="cta-ai-link">Ask Claude →</Link>
          </div>
        </Panel>
      </div>
    </div>
  );
}
