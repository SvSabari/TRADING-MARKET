import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { User, Wallet, ChartLineUp, ShieldCheck } from "@phosphor-icons/react";

export default function Profile() {
  const [profile, setProfile] = useState(null);
  const [funds, setFunds] = useState(null);
  const [orderStats, setOrderStats] = useState({ buy: 0, sell: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadData() {
      try {
        const profRes = await api.get("/brokers/profile");
        const fundRes = await api.get("/brokers/funds");
        const orderRes = await api.get("/orders").catch(() => ({ data: { orders: [] } }));
        
        if (profRes.data.error) throw new Error(profRes.data.error);
        if (fundRes.data.error) throw new Error(fundRes.data.error);

        if (profRes.data.profile) {
          setProfile(profRes.data.profile);
        }
        if (fundRes.data.funds) {
          const f = Array.isArray(fundRes.data.funds) ? fundRes.data.funds[0] : fundRes.data.funds;
          setFunds(f);
        }
        if (orderRes.data.orders) {
          const realOrders = orderRes.data.orders.filter(o => o.broker !== 'mock');
          const buys = realOrders.filter(o => o.side?.toUpperCase() === 'BUY').length;
          const sells = realOrders.filter(o => o.side?.toUpperCase() === 'SELL').length;
          setOrderStats({ buy: buys, sell: sells });
        }
      } catch (err) {
        setError(err.response?.data?.detail || err.response?.data?.error || err.message);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return <div className="p-6 text-[var(--text-secondary)]">Loading profile...</div>;
  }

  if (error) {
    return error.includes("No execution broker configured") ? <div className="p-6 text-[var(--text-primary)] font-medium text-sm">Welcome! Please connect an execution broker in the Settings tab to start trading.</div> : <div className="p-6 text-[var(--sell)] text-sm">Error: {error}</div>;
  }

  const toTitleCase = (str) => {
    if (!str) return str;
    return str.toString().toLowerCase().split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  };

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      <div>
        <h1 style={{ fontFamily: "Outfit", fontWeight: 900, fontSize: 28, letterSpacing: "-0.02em", color: "var(--text-primary)" }}>
          Dashboard & Funds
        </h1>
        <p className="dim mt-1">Manage your connected broker profile, wallet balances, and active margins.</p>
      </div>

      {/* Main Banner */}
      <div className="surface rounded-2xl border border-[var(--border)] overflow-hidden shadow-sm relative">
        <div className="absolute top-0 right-0 w-64 h-64 bg-[var(--brand)] opacity-[0.03] rounded-full blur-3xl -translate-y-1/2 translate-x-1/3"></div>
        <div className="p-8 flex flex-col md:flex-row justify-between items-start md:items-center gap-6 relative z-10">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-[var(--brand)] to-blue-600 flex items-center justify-center text-white shadow-lg shadow-[var(--brand)]/20">
              <User size={32} weight="duotone" />
            </div>
            <div>
              <h2 className="text-3xl font-bold font-outfit text-[var(--text-primary)]">
                {toTitleCase(profile?.accountName || profile?.clientName || profile?.name) || "Unknown Trader"}
              </h2>
              <div className="flex items-center gap-3 mt-2">
                <span className="px-2.5 py-1 bg-[var(--bg-primary)] rounded text-xs font-mono text-[var(--text-secondary)] border border-[var(--border)] shadow-inner flex items-center gap-1.5">
                  <ShieldCheck size={14} className="text-[var(--brand)]" />
                  ID: {profile?.accountId || profile?.clientId || profile?.id || "N/A"}
                </span>
                <span className="px-2 py-1 bg-green-500/10 text-green-500 rounded text-xs font-bold uppercase tracking-wider">
                  {profile?.accountStatus || "Active"}
                </span>
              </div>
            </div>
          </div>
          
          <div className="md:text-right bg-[var(--bg-primary)] p-4 rounded-xl border border-[var(--border)] shadow-inner min-w-[200px]">
            <p className="text-[10px] text-[var(--text-secondary)] uppercase tracking-widest mb-1 font-bold flex items-center md:justify-end gap-1.5">
              <Wallet size={14} /> Available Cash
            </p>
            <p className="text-4xl font-black text-green-500 font-outfit drop-shadow-sm">
              ₹{Number(funds?.cashmarginavailable || funds?.cash || funds?.net || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
            </p>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="surface p-5 rounded-xl border border-[var(--border)] flex flex-col shadow-sm hover:border-[var(--brand)]/30 transition-colors">
          <span className="text-[11px] text-[var(--text-secondary)] uppercase tracking-wider mb-2 font-semibold">Used Margin</span>
          <span className="text-2xl font-bold text-[var(--text-primary)] font-outfit">
            ₹{Number(funds?.cncMarginUsed || funds?.spanmargin || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
          </span>
        </div>
        <div className="surface p-5 rounded-xl border border-[var(--border)] flex flex-col shadow-sm hover:border-[var(--brand)]/30 transition-colors">
          <span className="text-[11px] text-[var(--text-secondary)] uppercase tracking-wider mb-2 font-semibold">Total Balance</span>
          <span className="text-2xl font-bold text-[var(--text-primary)] font-outfit">
            ₹{Number(funds?.net || funds?.subtotal || funds?.cashmarginavailable || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
          </span>
        </div>
        <div className="surface p-5 rounded-xl border border-[var(--border)] flex flex-col shadow-sm hover:border-[var(--brand)]/30 transition-colors">
          <span className="text-[11px] text-[var(--text-secondary)] uppercase tracking-wider mb-2 font-semibold flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[var(--brand)]"></span> Buy Orders
          </span>
          <span className="text-2xl font-bold text-[var(--brand)] font-outfit">{orderStats.buy}</span>
        </div>
        <div className="surface p-5 rounded-xl border border-[var(--border)] flex flex-col shadow-sm hover:border-[var(--brand)]/30 transition-colors">
          <span className="text-[11px] text-[var(--text-secondary)] uppercase tracking-wider mb-2 font-semibold flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[var(--sell)]"></span> Sell Orders
          </span>
          <span className="text-2xl font-bold text-[var(--sell)] font-outfit">{orderStats.sell}</span>
        </div>
      </div>

      {/* Account Details */}
      <div className="surface p-6 rounded-xl border border-[var(--border)] shadow-sm relative overflow-hidden">
        <h3 className="text-lg font-bold font-outfit text-[var(--text-primary)] mb-6 flex items-center gap-2">
          <ChartLineUp size={22} className="text-[var(--brand)]" weight="duotone" />
          Account Details
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-y-6 gap-x-8 relative z-10">
          {profile ? (() => {
            const friendlyLabels = {
              accountStatus: "Account Status",
              dpType: "DP Type",
              sBrokerName: "Broker Name",
              cellAddr: "Phone Number",
              emailAddr: "Email Address",
              exchEnabled: "Exchanges",
              poaStatus: "POA Status",
              product: "Products Allowed",
            };

            return Object.entries(profile)
              .filter(([k, v]) => typeof v !== 'object' && k !== 'accountName' && k !== 'accountId' && k !== 'accountStatus' && v)
              .map(([k, v]) => {
                const label = friendlyLabels[k] || k.replace(/([A-Z])/g, ' $1').trim();
                
                let displayValue = v?.toString();
                if (k === 'exchEnabled') {
                  displayValue = displayValue.split('|').filter(Boolean).map(e => e.toUpperCase().replace('_', ' ')).join(', ');
                } else if (k === 'emailAddr') {
                  displayValue = displayValue.toLowerCase();
                } else if (k === 'poaStatus') {
                  displayValue = displayValue === 'Y' ? 'Yes' : (displayValue === 'N' ? 'No' : displayValue);
                } else if (k === 'sBrokerName' || k === 'dpType') {
                  displayValue = toTitleCase(displayValue);
                  if (displayValue === 'Na') displayValue = 'N/A';
                } else if (Array.isArray(v)) {
                  displayValue = v.join(', ');
                }
                
                return (
                  <div key={k} className="flex flex-col gap-1">
                    <span className="text-[11px] text-[var(--text-secondary)] uppercase tracking-wider font-semibold capitalize">{label}</span>
                    <span className="text-[var(--text-primary)] font-medium text-sm">
                      {displayValue}
                    </span>
                  </div>
                );
              });
          })() : (
            <div className="text-sm text-[var(--text-secondary)] italic">No additional profile details available.</div>
          )}
        </div>
      </div>
    </div>
  );
}

