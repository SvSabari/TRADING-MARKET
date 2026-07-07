import { useMemo, useState } from "react";
import { toast } from "sonner";
import { API } from "@/lib/api";
import Panel from "@/components/Panel";
import { Robot, PaperPlaneTilt } from "@phosphor-icons/react";

const SUGGESTIONS = [
  "Explain a long buildup signal and how I should size into it.",
  "What's the difference between max pain and PCR for Nifty?",
  "Summarise the risk of a gamma scalping strategy on bank nifty.",
  "How should I interpret an OI breakout with low IV?",
];

// One stable id per page-load, computed outside the component to keep AI() pure.
const SESSION_ID = "ui-" + Math.random().toString(36).slice(2, 9);

export default function AI() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const sessionId = useMemo(() => SESSION_ID, []);

  const send = async (text) => {
    if (!text) return;
    setMessages((m) => [...m, { role: "user", text }, { role: "assistant", text: "" }]);
    setInput("");
    setBusy(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API}/ai/explain`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ prompt: text, session_id: sessionId }),
      });
      if (!res.ok) throw new Error("Stream error");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = { role: "assistant", text: copy[copy.length - 1].text + chunk };
          return copy;
        });
      }
    } catch (e) {
      toast.error("AI request failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-4" data-testid="ai-page">
      <div>
        <h1 style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 28, letterSpacing: "-0.02em" }}>AI assistant.</h1>
        <p className="dim text-sm mt-1">Powered by Claude Sonnet 4.5 · streams tokens directly into your terminal.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <Panel title="Suggestions" kicker="quick prompts" className="lg:col-span-1">
          <div className="cell-divider">
            {SUGGESTIONS.map((s) => (
              <button key={s} className="text-left p-4 hover:bg-[#1A1A1A] w-full text-xs dim hover:text-white transition" onClick={() => send(s)} data-testid={`ai-suggestion-${s.slice(0, 10)}`}>
                {s}
              </button>
            ))}
          </div>
        </Panel>

        <Panel title="Conversation" kicker={sessionId} className="lg:col-span-3">
          <div className="p-4 space-y-3 max-h-[420px] overflow-y-auto" data-testid="ai-messages">
            {messages.length === 0 && (
              <div className="dim text-xs flex items-center gap-2">
                <Robot size={16} weight="bold" /> Ask Claude anything about your signals, positions or strategies.
              </div>
            )}
            {messages.map((m, i) => (
              <div key={`${m.role}-${i}-${m.text.slice(0, 12)}`} className="space-y-1">
                <div className="dim text-[10px] mono uppercase tracking-widest">{m.role === "user" ? "you" : "claude · sonnet 4.5"}</div>
                <div className={`whitespace-pre-wrap text-sm ${m.role === "user" ? "" : "buy"}`} style={{ fontFamily: m.role === "user" ? "IBM Plex Sans" : "IBM Plex Sans" }}>
                  {m.text || (busy && i === messages.length - 1 ? <span className="dim">streaming…</span> : "")}
                </div>
              </div>
            ))}
          </div>
          <form className="border-t border-[#222] p-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); send(input); }}>
            <input className="terminal" placeholder="Ask Claude…" data-testid="ai-input" value={input} onChange={(e) => setInput(e.target.value)} disabled={busy} />
            <button className="btn btn-primary" disabled={busy || !input} data-testid="ai-send-btn">
              <PaperPlaneTilt size={14} weight="bold" /> Send
            </button>
          </form>
        </Panel>
      </div>
    </div>
  );
}
