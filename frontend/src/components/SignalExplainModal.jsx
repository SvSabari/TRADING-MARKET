import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtNum } from "@/lib/format";
import { Brain, X } from "@phosphor-icons/react";

/** Modal-style overlay that explains a signal via Claude Sonnet 4.5.
 *  Fires the /ai/explain-signal endpoint on mount.
 */
export default function SignalExplainModal({ signal, onClose }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const { data } = await api.post("/ai/explain-signal", {
          symbol: signal.symbol,
          kind: signal.kind,
          price: signal.price,
          change_pct: signal.change_pct,
          volume_ratio: signal.volume_ratio,
          confidence: signal.confidence,
          ts: signal.ts,
        });
        if (!cancel) setData(data);
      } catch (e) {
        if (!cancel) setError(e?.response?.data?.detail || "AI request failed");
      } finally {
        if (!cancel) setBusy(false);
      }
    })();
    return () => { cancel = true; };
  }, [signal]);

  const r = data || {};
  const sideClass = r.side_bias === "SELL" ? "sell" : r.side_bias === "BUY" ? "buy" : "warn";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.85)", backdropFilter: "blur(12px)" }}
      data-testid="signal-explain-modal"
      onClick={onClose}
    >
      <div
        className="panel max-w-lg w-full"
        style={{ background: "#0F0F0F", border: "1px solid #222" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="panel-h">
          <div className="flex items-center gap-2">
            <Brain size={14} weight="bold" />
            <span>AI explainer</span>
            <span className="kicker">· {signal.symbol} · {signal.kind.replace("_", " ")}</span>
          </div>
          <button
            data-testid="signal-explain-close"
            onClick={onClose}
            className="dim hover:text-white transition-colors"
          >
            <X size={14} weight="bold" />
          </button>
        </div>

        <div className="p-5 space-y-4 text-xs">
          {busy && (
            <div className="dim mono uppercase tracking-widest animate-pulse">
              Claude Sonnet 4.5 is analysing the tape…
            </div>
          )}
          {error && <div className="sell mono">{error}</div>}
          {data && (
            <>
              <div>
                <div className="dim text-[10px] mono uppercase tracking-widest mb-1">Reasoning</div>
                <div data-testid="signal-explain-reasoning" className="leading-relaxed">
                  {r.reasoning}
                </div>
              </div>
              <div className="grid grid-cols-3 gap-px bg-[#222]">
                <div className="bg-[#121212] p-3">
                  <div className="dim text-[10px] mono uppercase tracking-widest">Stop loss</div>
                  <div className="mt-1 num text-base sell" data-testid="signal-explain-sl">
                    ₹{fmtNum(r.suggested_sl)}
                  </div>
                </div>
                <div className="bg-[#121212] p-3">
                  <div className="dim text-[10px] mono uppercase tracking-widest">Target</div>
                  <div className="mt-1 num text-base buy" data-testid="signal-explain-tgt">
                    ₹{fmtNum(r.suggested_target)}
                  </div>
                </div>
                <div className="bg-[#121212] p-3">
                  <div className="dim text-[10px] mono uppercase tracking-widest">R : R</div>
                  <div className="mt-1 num text-base">{fmtNum(r.risk_reward)}</div>
                </div>
              </div>
              <div className="flex items-center justify-between border-t border-[#222] pt-3">
                <div className="dim text-[10px] mono uppercase tracking-widest">Bias</div>
                <div className={`mono uppercase tracking-widest text-[11px] ${sideClass}`}>
                  {r.side_bias} · {(r.confidence_score * 100).toFixed(0)}%
                </div>
              </div>
              <div className="dim text-[10px] mono uppercase tracking-widest opacity-60">
                model: {r.model || "claude-sonnet-4-5"}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
