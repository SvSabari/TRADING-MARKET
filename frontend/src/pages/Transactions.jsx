import { useState } from "react";
import Panel from "@/components/Panel";
import { CheckCircle, Clock, XCircle, ArrowDownLeft, ArrowUpRight } from "@phosphor-icons/react";

const MOCK_TRANSACTIONS = [
  { id: "TXN-99812", date: "2026-09-28 14:30:00", type: "DEPOSIT", amount: 50000, status: "COMPLETED", method: "UPI" },
  { id: "TXN-99811", date: "2026-09-27 09:15:00", type: "WITHDRAWAL", amount: 15000, status: "PENDING", method: "Bank Transfer" },
  { id: "TXN-99810", date: "2026-09-25 11:20:00", type: "FEE", amount: 499, status: "COMPLETED", method: "Wallet" },
  { id: "TXN-99809", date: "2026-09-20 16:45:00", type: "DEPOSIT", amount: 100000, status: "COMPLETED", method: "Net Banking" },
  { id: "TXN-99808", date: "2026-09-18 10:05:00", type: "WITHDRAWAL", amount: 25000, status: "FAILED", method: "Bank Transfer" }
];

export default function Transactions() {
  const [txns] = useState(MOCK_TRANSACTIONS);

  return (
    <div className="p-4 space-y-4 h-full overflow-y-auto" data-testid="transactions-page">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h1 style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 28, letterSpacing: "-0.02em" }}>Ledger & Transactions.</h1>
          <p className="dim text-sm mt-1">View your deposits, withdrawals, and platform fee deductions.</p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-outline border-dashed text-xs">+ Add Funds</button>
          <button className="btn btn-outline border-dashed text-xs">Withdraw</button>
        </div>
      </div>

      <Panel title="Transaction History" kicker={txns.length + " records"}>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-widest text-[var(--text-secondary)]">
                <th className="py-3 px-4">Date</th>
                <th className="py-3 px-4">Transaction ID</th>
                <th className="py-3 px-4">Type</th>
                <th className="py-3 px-4">Method</th>
                <th className="py-3 px-4 text-right">Amount (?)</th>
                <th className="py-3 px-4 text-center">Status</th>
              </tr>
            </thead>
            <tbody>
              {txns.map((t) => (
                <tr key={t.id} className="border-b border-[var(--border)] hover:bg-[var(--surface-hover)] transition-colors">
                  <td className="py-3 px-4 text-xs font-mono">{t.date}</td>
                  <td className="py-3 px-4 text-xs font-mono text-[var(--brand)]">{t.id}</td>
                  <td className="py-3 px-4 text-xs">
                    <div className="flex items-center gap-1.5 font-bold">
                      {t.type === "DEPOSIT" ? <ArrowDownLeft size={14} color="var(--buy)" /> : 
                       t.type === "WITHDRAWAL" ? <ArrowUpRight size={14} color="var(--sell)" /> : 
                       <Clock size={14} color="var(--text-secondary)" />}
                      <span style={{ color: t.type === "DEPOSIT" ? "var(--buy)" : t.type === "WITHDRAWAL" ? "var(--sell)" : "var(--text-primary)" }}>
                        {t.type}
                      </span>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-xs dim">{t.method}</td>
                  <td className="py-3 px-4 text-xs font-mono text-right font-bold">?{t.amount.toLocaleString()}</td>
                  <td className="py-3 px-4 text-xs flex justify-center">
                    {t.status === "COMPLETED" && <span className="bg-green-500/20 text-green-600 px-2 py-0.5 rounded font-bold tracking-widest text-[9px] flex items-center gap-1"><CheckCircle weight="bold"/> {t.status}</span>}
                    {t.status === "PENDING" && <span className="bg-yellow-500/20 text-yellow-600 px-2 py-0.5 rounded font-bold tracking-widest text-[9px] flex items-center gap-1"><Clock weight="bold"/> {t.status}</span>}
                    {t.status === "FAILED" && <span className="bg-red-500/20 text-red-600 px-2 py-0.5 rounded font-bold tracking-widest text-[9px] flex items-center gap-1"><XCircle weight="bold"/> {t.status}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
