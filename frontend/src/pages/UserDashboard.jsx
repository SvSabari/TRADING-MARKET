import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { Lightning, SignOut, CheckCircle, Clock, Plugs, Receipt, ArrowClockwise, XCircle, User, ShieldCheck, Wallet } from "@phosphor-icons/react";

function DashboardFunds() {
  const [profile, setProfile] = useState(null);
  const [funds, setFunds] = useState(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState(null);

  useEffect(() => {
    async function loadData() {
      try {
        const profRes = await api.get("/brokers/profile").catch((e) => ({ data: { error: e.message } }));
        const fundRes = await api.get("/brokers/funds").catch((e) => ({ data: { error: e.message } }));
        
        if (profRes.data.error || fundRes.data.error) {
          setErrorMsg(profRes.data.error || fundRes.data.error);
        }
        
        if (profRes.data.profile) setProfile(profRes.data.profile);
        if (fundRes.data.funds) {
          const f = Array.isArray(fundRes.data.funds) ? fundRes.data.funds[0] : fundRes.data.funds;
          setFunds(f);
        }
      } catch (err) {
        setErrorMsg(err.message);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const toTitleCase = (str) => {
    if (!str) return str;
    return str.toString().toLowerCase().split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  };

  if (loading) return <div className="text-xs dim italic mb-2">Loading dashboard funds...</div>;
  if (errorMsg) return <div className="text-xs text-red-500 bg-red-500/10 p-2 rounded border border-red-500/20 mb-2">Error loading funds: {errorMsg}</div>;
  if (!profile && !funds) return <div className="text-xs text-yellow-500 bg-yellow-500/10 p-2 rounded border border-yellow-500/20 mb-2">No profile or funds data returned from broker.</div>;

  return (
    <div className="space-y-2 mb-2">
      {/* Main Banner */}
      <div className="surface rounded-lg border border-[var(--border)] overflow-hidden shadow-sm relative">
        <div className="absolute top-0 right-0 w-24 h-24 bg-[var(--brand)] opacity-[0.03] rounded-full blur-2xl -translate-y-1/2 translate-x-1/3"></div>
        <div className="p-3 flex flex-col md:flex-row justify-between items-start md:items-center gap-3 relative z-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[var(--brand)] to-blue-600 flex items-center justify-center text-white shadow-lg shadow-[var(--brand)]/20">
              <User size={20} weight="duotone" />
            </div>
            <div>
              <h2 className="text-sm font-bold font-outfit text-[var(--text-primary)]">
                {toTitleCase(profile?.accountName || profile?.clientName || profile?.name) || "Connected Trader"}
              </h2>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="px-2 py-0.5 bg-[var(--bg-primary)] rounded text-[10px] font-mono text-[var(--text-secondary)] border border-[var(--border)] shadow-inner flex items-center gap-1">
                  <ShieldCheck size={12} className="text-[var(--brand)]" />
                  ID: {profile?.accountId || profile?.clientId || profile?.id || "N/A"}
                </span>
                <span className="px-2 py-0.5 bg-green-500/10 text-green-500 rounded text-[10px] font-bold uppercase tracking-wider">
                  {profile?.accountStatus || "Active"}
                </span>
              </div>
            </div>
          </div>
          
          <div className="md:text-right bg-[var(--bg-primary)] p-2 px-3 rounded-lg border border-[var(--border)] shadow-inner">
            <p className="text-[9px] text-[var(--text-secondary)] uppercase tracking-widest mb-0.5 font-bold flex items-center md:justify-end gap-1">
              <Wallet size={12} /> Available Cash
            </p>
            <p className="text-lg font-black text-green-500 font-outfit drop-shadow-sm">
              ₹{Number(funds?.cashmarginavailable || funds?.cash || funds?.net || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
            </p>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-2">
        <div className="surface p-3 rounded-lg border border-[var(--border)] flex flex-col shadow-sm">
          <span className="text-[9px] text-[var(--text-secondary)] uppercase tracking-wider mb-1 font-semibold">Used Margin</span>
          <span className="text-md font-bold text-[var(--text-primary)] font-outfit">
            ₹{Number(funds?.cncMarginUsed || funds?.spanmargin || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
          </span>
        </div>
        <div className="surface p-3 rounded-lg border border-[var(--border)] flex flex-col shadow-sm">
          <span className="text-[9px] text-[var(--text-secondary)] uppercase tracking-wider mb-1 font-semibold">Total Balance</span>
          <span className="text-md font-bold text-[var(--text-primary)] font-outfit">
            ₹{Number(funds?.net || funds?.subtotal || funds?.cashmarginavailable || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function UserDashboard() {
  const { user, logout } = useAuth();
  const [brokers, setBrokers] = useState([]);
  const [orders, setOrders] = useState([]);
  const [busyBroker, setBusyBroker] = useState("");
  const [tokenInputs, setTokenInputs] = useState({});
  const [loadingOrders, setLoadingOrders] = useState(false);
  const [confirmReconnect, setConfirmReconnect] = useState(null);

  const loadData = async () => {
    try {
      const [bRes, oRes] = await Promise.allSettled([
        api.get("/managed-users/me/brokers"),
        api.get("/managed-users/me/orders"),
      ]);

      if (bRes.status === "fulfilled") {
        setBrokers(bRes.value.data.brokers || []);
      }
      if (oRes.status === "fulfilled") {
        setOrders(oRes.value.data.orders || []);
      }
    } catch (err) {
      toast.error("Failed to load user portal data");
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  const generateBrokerSession = async (bName) => {
    setConfirmReconnect(null);
    setBusyBroker(bName);
    try {
      const { data } = await api.post(`/managed-users/me/get-session/${bName}`);
      if (data.login_url) {
        window.location.href = data.login_url;
        toast.success(`Opening ${data.broker} authentication page…`);
      } else {
        toast.success(`${data.broker} connected successfully!`);
      }
      loadData();
    } catch (err) {
      toast.error(err?.response?.data?.detail || `Failed to start session for ${bName}`);
    } finally {
      setBusyBroker("");
    }
  };

  const submitSessionToken = async (bName) => {
    const token = tokenInputs[bName];
    if (!token) return toast.error("Please enter the session token or auth code");
    
    setBusyBroker(bName);
    try {
      await api.post(`/managed-users/me/save-session/${bName}`, { session_token: token });
      toast.success(`${bName} token saved successfully!`);
      setTokenInputs(prev => ({ ...prev, [bName]: "" }));
      loadData();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to save session token");
    } finally {
      setBusyBroker("");
    }
  };

  const getBrokerBadgeColor = (bName) => {
    const name = (bName || "").toLowerCase();
    if (name.includes("alice")) return "#009688";
    if (name.includes("zerodha") || name.includes("kite")) return "#FF5722";
    if (name.includes("icici")) return "#3F51B5";
    if (name.includes("angel")) return "#E91E63";
    if (name.includes("upstox")) return "#9C27B0";
    return "var(--brand)";
  };

  return (
    <div className="h-screen flex flex-col p-3 max-w-7xl mx-auto space-y-3 overflow-hidden" style={{ background: "var(--bg)" }}>
      {/* Header */}
      <div className="flex items-center justify-between p-2 rounded-lg shadow-sm shrink-0" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded flex items-center justify-center font-bold text-sm" style={{ background: "var(--brand)", color: "#FFF", fontFamily: "Outfit" }}>
            {user?.name?.[0]?.toUpperCase() || "U"}
          </div>
          <div>
            <div style={{ fontFamily: "Outfit", fontWeight: 700, fontSize: 14 }} className="flex items-center gap-2">
              <span>{user?.name}</span>
              <span className="text-[9px] mono uppercase tracking-wider px-1.5 py-0.5 rounded font-bold" style={{ background: "rgba(42,157,143,0.12)", color: "var(--buy)" }}>
                Active
              </span>
            </div>
            <div className="dim text-[10px] mono tracking-widest uppercase">Sub-Account User Portal</div>
          </div>
        </div>
        <button className="btn btn-outline text-[11px] px-3 py-1" onClick={logout}>
          <SignOut size={12} weight="bold" /> Logout
        </button>
      </div>

      {/* Main Content Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-4 flex-1 min-h-0 overflow-hidden">
        
        {/* Section 1: Broker Connections */}
        <div className="space-y-3 flex flex-col h-full overflow-y-auto pr-1">
          <div className="flex items-center justify-between shrink-0">
            <div>
              <h2 style={{ fontFamily: "Outfit", fontWeight: 700, fontSize: 16 }} className="flex items-center gap-2">
                <Plugs size={18} weight="bold" style={{ color: "var(--brand)" }} /> Broker Connections
              </h2>
            </div>
            <button className="btn btn-outline text-[10px] px-2 py-1" onClick={loadData} title="Refresh Status">
              <ArrowClockwise size={12} weight="bold" /> Refresh
            </button>
          </div>

          <DashboardFunds />

          {brokers.length === 0 ? (
            <div className="p-4 text-center dim text-xs border rounded-lg border-dashed" style={{ borderColor: "var(--border)" }}>
              No brokers assigned.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {brokers.map((b, i) => {
                const isGen = b.session_generated;
                const badgeColor = getBrokerBadgeColor(b.broker);
                return (
                  <div key={i} className="p-3 rounded-lg border flex flex-col justify-between" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
                    <div className="flex items-center justify-between mb-3">
                      <div className="px-2 py-0.5 rounded text-[10px] font-bold uppercase mono tracking-widest" style={{ background: badgeColor, color: "white" }}>
                        {b.broker}
                      </div>
                      <span className="flex items-center gap-1 text-[10px] font-bold uppercase mono tracking-widest" style={{ color: isGen ? "var(--buy)" : "var(--sell)" }}>
                        {isGen ? <CheckCircle size={12} weight="fill" /> : <XCircle size={12} weight="fill" />}
                        {isGen ? "Active" : "Disconnected"}
                      </span>
                    </div>

                    <div className="space-y-1 text-xs font-mono mb-4">
                      <div className="dim">Account No: <span className="text-[var(--text-primary)] font-bold">{b.account_number || "—"}</span></div>
                      <div className="dim">API Key: <span className="text-[var(--text-primary)]">{b.api_key ? b.api_key.slice(0, 8) + "…" : "—"}</span></div>
                      {b.session_date && <div className="dim text-[10px]">Active Since: {b.session_date}</div>}
                    </div>

                    <div className="space-y-2">
                      <button className="btn btn-primary w-full justify-center py-2 text-[10px] font-bold uppercase tracking-wider" onClick={() => isGen ? setConfirmReconnect(b.broker) : generateBrokerSession(b.broker)} disabled={busyBroker === b.broker}>
                        <Lightning size={12} weight="bold" />
                        {busyBroker === b.broker ? "Processing…" : isGen ? "Reconnect Broker" : "1. Authenticate (Login)"}
                      </button>
                      {!isGen && (
                        <div className="flex gap-2">
                          <input
                            type="text"
                            placeholder="Paste Code/Token"
                            className="input flex-1 text-[10px] mono py-1"
                            value={tokenInputs[b.broker] || ""}
                            onChange={(e) => setTokenInputs(prev => ({ ...prev, [b.broker]: e.target.value }))}
                          />
                          <button 
                            className="btn btn-outline text-[10px] px-2 py-1"
                            onClick={() => submitSessionToken(b.broker)}
                            disabled={busyBroker === b.broker}
                          >
                            Submit
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Section 2: Mirrored Trades */}
        <div className="space-y-3 flex flex-col h-full overflow-hidden">
          <div className="flex items-center justify-between shrink-0">
            <h2 className="text-lg font-bold font-outfit text-[var(--text-primary)] flex items-center gap-2">
              <Receipt size={22} className="text-[var(--brand)]" weight="duotone" />
              Mirrored Trades & Orders
            </h2>
            <div className="text-[10px] mono font-bold dim">{orders.length} Total Orders</div>
          </div>

          <div className="surface rounded-lg border border-[var(--border)] flex-1 overflow-hidden flex flex-col shadow-sm">
            <div className="overflow-y-auto flex-1 p-0 custom-scrollbar">
              <table className="w-full text-left text-sm">
              <thead>
                <tr className="dim text-[10px] uppercase tracking-widest border-b border-[var(--border)]" style={{ background: "var(--bg)" }}>
                  <th className="text-left py-3 px-4">Time</th>
                  <th className="text-left py-3 px-4">Symbol</th>
                  <th className="text-center py-3 px-4">Side</th>
                  <th className="text-right py-3 px-4">Qty</th>
                  <th className="text-right py-3 px-4">Price</th>
                  <th className="text-left py-3 px-4">Broker</th>
                  <th className="text-center py-3 px-4">Status</th>
                  <th className="text-right py-3 px-4">P&L</th>
                </tr>
              </thead>
              <tbody className="cell-divider">
                {orders.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="p-8 text-center dim text-xs">
                      No orders executed yet. Executed trades will appear here automatically.
                    </td>
                  </tr>
                ) : (
                  orders.map((o) => {
                    const isBuy = (o.side || "").toUpperCase() === "BUY";
                    const pnl = o.pnl || 0;
                    return (
                      <tr key={o.id} className="hover:bg-[rgba(255,255,255,0.02)] transition-colors">
                        <td className="py-3 px-4 mono dim text-[11px]">
                          {o.placed_at ? new Date(o.placed_at).toLocaleTimeString() : "—"}
                        </td>
                        <td className="py-3 px-4 font-bold mono">{o.symbol}</td>
                        <td className="py-3 px-4 text-center">
                          <span className="px-2 py-0.5 rounded text-[10px] mono font-bold" style={{
                            background: isBuy ? "rgba(42,157,143,0.12)" : "rgba(231,111,81,0.12)",
                            color: isBuy ? "var(--buy)" : "var(--sell)",
                          }}>
                            {o.side}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right mono font-bold">{o.qty}</td>
                        <td className="py-3 px-4 text-right mono">₹{o.price?.toFixed(2)}</td>
                        <td className="py-3 px-4 mono uppercase text-[10px] font-bold dim">{o.broker}</td>
                        <td className="py-3 px-4 text-center">
                          <span className="text-[10px] mono font-bold uppercase px-2 py-0.5 rounded" style={{
                            background: o.status === "FILLED" ? "rgba(42,157,143,0.12)" : "rgba(255,255,255,0.05)",
                            color: o.status === "FILLED" ? "var(--buy)" : "var(--text-secondary)",
                          }}>
                            {o.status}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right mono font-bold whitespace-nowrap">
                          {(() => {
                            const pnl = o.pnl ?? 0;
                            const isOpen = o.unrealized;
                            const color = pnl > 0 ? "var(--buy)" : pnl < 0 ? "var(--sell)" : "var(--text-secondary)";
                            const sign = pnl > 0 ? "+" : "";
                            return (
                              <span style={{ color }}>
                                {sign}₹{Math.abs(pnl).toFixed(2)}
                                {isOpen && <span className="text-[9px] dim ml-1 opacity-60">(open)</span>}
                              </span>
                            );
                          })()}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      {/* End of Main Content Sections Grid */}
      </div>

      {confirmReconnect && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="p-6 rounded-lg w-full max-w-sm" style={{ background: "var(--surface)", border: "1px solid var(--border)", boxShadow: "var(--shadow-lg)" }}>
            <h3 className="font-bold text-lg mb-2" style={{ color: "var(--text-primary)" }}>Already Connected</h3>
            <p className="text-sm mb-6" style={{ color: "var(--text-secondary)" }}>
              <strong className="text-[var(--text-primary)] uppercase font-mono tracking-widest">{confirmReconnect}</strong> is already actively connected. Reconnecting will disconnect the current active session. Do you want to proceed?
            </p>
            <div className="flex items-center justify-end gap-3">
              <button className="btn py-2 px-4" onClick={() => setConfirmReconnect(null)}>Cancel</button>
              <button className="btn py-2 px-4" style={{ background: "var(--brand)", color: "white", border: "none" }} onClick={() => generateBrokerSession(confirmReconnect)}>Reconnect</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
