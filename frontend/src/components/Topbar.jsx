import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Bell, SignOut, User, List } from "@phosphor-icons/react";
import { getMarketStatus } from "@/lib/marketHours";

export default function Topbar() {
  const { user, logout } = useAuth();
  const [unread, setUnread] = useState(0);
  const [mktStatus, setMktStatus] = useState(getMarketStatus());

  useEffect(() => {
    const tick = () => setMktStatus(getMarketStatus());
    tick();
    const i = setInterval(tick, 30000); // recheck every 30s
    return () => clearInterval(i);
  }, []);

  useEffect(() => {
    let cancel = false;
    const fetchNotifs = async () => {
      try {
        const { data } = await api.get("/notifications?limit=1");
        if (!cancel) setUnread(data.unread || 0);
      } catch (e) { console.error("api fetch failed:", e); }
    };
    fetchNotifs();
    const i2 = setInterval(fetchNotifs, 5000);
    return () => { cancel = true; clearInterval(i2); };
  }, []);

  const toggleSidebar = () => {
    window.leftCollapsed = !window.leftCollapsed;
    const el = document.querySelector('.app-shell');
    if (el) el.classList.toggle('left-collapsed');
  };

  return (
    <div className="flex-1 flex items-center gap-6 min-w-0" data-testid="topbar">
      <button onClick={toggleSidebar} className="btn-ghost btn shrink-0 px-2 mr-2" title="Toggle Sidebar">
        <List color="white" size={18} weight="bold" />
      </button>
      <div className="flex items-center gap-2 shrink-0">
        <span className="dot" style={{ background: mktStatus.color }}></span>
        <span className="mono text-xs text-white uppercase tracking-widest" style={{ color: "white" }}>
          {mktStatus.label} · {new Date().toLocaleDateString("en-IN")}
        </span>
      </div>
      <div className="flex-1 flex justify-center items-center overflow-hidden" data-testid="project-title">
        <span className="text-white text-xl" style={{ fontFamily: "Montserrat, sans-serif", fontWeight: 900, letterSpacing: "0.15em", textShadow: "0 2px 10px rgba(0,0,0,0.15)" }}>TRADERS PRO</span>
      </div>
      <Link to="/notifications" data-testid="notifications-btn" className="btn-ghost btn relative shrink-0">
        <Bell color="white" size={14} weight="bold" />
        {unread > 0 && (
          <span className="absolute -top-1.5 -right-1.5 bg-[#FF3B30] text-white font-bold text-[9px] min-w-[16px] h-[16px] flex items-center justify-center rounded-full px-1 shadow-sm" data-testid="notif-unread-count">
            {unread}
          </span>
        )}
      </Link>
      <div className="flex items-center gap-2 shrink-0">
        <User color="white" size={14} weight="bold" />
        <span className="mono text-xs text-white" data-testid="topbar-user-email">{user?.email}</span>
        <button className="btn btn-ghost" onClick={logout} data-testid="logout-btn">
          <SignOut color="white" size={14} weight="bold" />
        </button>
      </div>
    </div>
  );
}
