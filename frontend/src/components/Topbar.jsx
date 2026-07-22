import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { fmtNum, fmtPct } from "@/lib/format";
import { Bell, SignOut, User } from "@phosphor-icons/react";

export default function Topbar() {
  const { user, logout } = useAuth();
  const [ticks, setTicks] = useState([]);
  const [prevPrices, setPrevPrices] = useState({});
  const [unread, setUnread] = useState(0);
  useEffect(() => {
    let cancel = false;
    const fetchSnap = async () => {
      try {
        const { data } = await api.get("/market/snapshot");
        if (cancel) return;
        const sorted = [...data.ticks].sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct)).slice(0, 14);
        setTicks((curr) => {
          // before updating, copy current ltps into prevPrices for flash class
          const snap = {};
          curr.forEach((t) => { snap[t.symbol] = t.ltp; });
          setPrevPrices(snap);
          return sorted;
        });
      } catch (e) { console.error("api fetch failed:", e); }
    };
    const fetchNotifs = async () => {
      try {
        const { data } = await api.get("/notifications?limit=1");
        if (!cancel) setUnread(data.unread || 0);
      } catch (e) { console.error("api fetch failed:", e); }
    };
    fetchSnap(); fetchNotifs();
    const i1 = setInterval(fetchSnap, 2000);
    const i2 = setInterval(fetchNotifs, 5000);
    return () => { cancel = true; clearInterval(i1); clearInterval(i2); };
  }, []);

  return (
    <div className="flex-1 flex items-center gap-6 min-w-0" data-testid="topbar">
      <div className="flex items-center gap-2 shrink-0">
        <span className="dot dot-live"></span>
        <span className="mono text-xs dim uppercase tracking-widest">live · {new Date().toLocaleDateString("en-IN")}</span>
      </div>
      <div className="ticker-row flex-1 overflow-hidden" data-testid="ticker-row">
        {ticks.map((t) => {
          const prevPx = prevPrices[t.symbol];
          const flash = prevPx ? (t.ltp > prevPx ? "flash-up" : t.ltp < prevPx ? "flash-dn" : "") : "";
          const color = t.change_pct >= 0 ? "buy" : "sell";
          return (
            <span key={t.symbol} className={`ticker-item ${flash} px-1`} data-testid={`ticker-${t.symbol}`}>
              <span className="dim">{t.symbol}</span>
              <span>{fmtNum(t.ltp)}</span>
              <span className={color}>{fmtPct(t.change_pct, 2)}</span>
            </span>
          );
        })}
      </div>
      <Link to="/notifications" data-testid="notifications-btn" className="btn-ghost btn relative shrink-0">
        <Bell size={14} weight="bold" />
        {unread > 0 && (
          <span className="absolute -top-1.5 -right-1.5 bg-[#FF3B30] text-white font-bold text-[9px] min-w-[16px] h-[16px] flex items-center justify-center rounded-full px-1 shadow-sm" data-testid="notif-unread-count">
            {unread}
          </span>
        )}
      </Link>
      <div className="flex items-center gap-2 shrink-0">
        <User size={14} weight="bold" />
        <span className="mono text-xs" data-testid="topbar-user-email">{user?.email}</span>
        <button className="btn btn-ghost" onClick={logout} data-testid="logout-btn">
          <SignOut size={14} weight="bold" />
        </button>
      </div>
    </div>
  );
}
