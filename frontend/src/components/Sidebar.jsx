import { NavLink } from "react-router-dom";
import { useAuth } from "@/lib/auth-context";
import { useEffect, useState } from "react";
import {
  ChartBar, Lightning, Strategy, ChartLine, Wallet, Receipt, TestTube,
  Database, Robot, Plugs, Gear, Pulse, Crosshair, Users, SquaresFour
} from "@phosphor-icons/react";
import { getMarketStatus } from "@/lib/marketHours";

const TRADER_NAV = [
  { to: "/", label: "Dashboard", icon: ChartBar, testid: "nav-dashboard" },
  { to: "/signals", label: "Signals", icon: Lightning, testid: "nav-signals" },
  { to: "/tradingview", label: "TradingView", icon: Pulse, testid: "nav-tradingview" },
  { to: "/strategies", label: "Strategies", icon: Strategy, testid: "nav-strategies" },
  { to: "/option-chain", label: "Option Chain", icon: ChartLine, testid: "nav-option-chain" },
  { to: "/premium-matcher", label: "Premium Matcher", icon: Crosshair, testid: "nav-premium-matcher" },
  { to: "/positions", label: "Positions", icon: Wallet, testid: "nav-positions" },
  { to: "/orders", label: "Trade Book", icon: Receipt, testid: "nav-orders" },
  { to: "/backtest", label: "Backtest", icon: TestTube, testid: "nav-backtest" },
  { to: "/parquet", label: "Parquet Data", icon: Database, testid: "nav-parquet" },
  { to: "/chart", label: "Charts", icon: ChartLine, testid: "nav-chart" },
  { to: "/heatmap", label: "Heatmap", icon: SquaresFour, testid: "nav-heatmap" },
  { to: "/ai", label: "AI Assistant", icon: Robot, testid: "nav-ai" },
  { to: "/brokers", label: "Brokers", icon: Plugs, testid: "nav-brokers" },
  { to: "/user-management", label: "User Management", icon: Users, testid: "nav-user-management" },
  { to: "/settings", label: "Settings", icon: Gear, testid: "nav-settings" },
];

export default function Sidebar() {
  const { user, isTrader } = useAuth();
  const nav = isTrader ? TRADER_NAV : [];
  const [mktStatus, setMktStatus] = useState(getMarketStatus());

  useEffect(() => {
    const tick = () => setMktStatus(getMarketStatus());
    tick();
    const i = setInterval(tick, 30000); // recheck every 30s
    return () => clearInterval(i);
  }, []);

  return (
    <div data-testid="sidebar" className="flex flex-col h-full">
      <NavLink to="/profile" className="px-4 py-4 border-b flex items-center gap-2 hover:bg-gray-50/5 cursor-pointer transition-colors" style={{ textDecoration: 'none' }}>
        <div className="w-8 h-8 rounded-full flex items-center justify-center shadow-sm" style={{ backgroundColor: 'var(--brand)', color: '#fff', fontFamily: "Outfit", fontWeight: 700, fontSize: 16 }}>
          {user?.name ? user.name.charAt(0).toUpperCase() : 'T'}
        </div>
        <div>
          <div className="truncate max-w-[150px]" style={{ fontFamily: "Outfit", fontWeight: 700, fontSize: 15, letterSpacing: "-0.01em", color: 'var(--text-primary)' }}>
            {user?.name?.toUpperCase() || 'TRADE'}
          </div>
          <div className="text-[10px] uppercase tracking-widest mono" style={{ color: 'var(--brand)' }}>Profile & Funds</div>
        </div>
      </NavLink>
      <nav className="flex-1 py-2 overflow-y-auto custom-scrollbar">
        {nav.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.to === "/"}
            data-testid={n.testid}
            className={({ isActive }) => `sidebar-link ${isActive ? "active" : ""}`}
          >
            <n.icon size={14} weight="bold" />
            <span>{n.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="px-4 py-3 border-t">
        <div className="dim text-[10px] uppercase tracking-widest mono mb-1">market</div>
        <div className="flex items-center gap-2 text-xs mono" style={{ color: mktStatus.open ? undefined : mktStatus.color }}>
          <span className="dot" style={{ background: mktStatus.color }}></span>
          <span>NSE · {mktStatus.label}</span>
        </div>
      </div>
    </div>
  );
}
