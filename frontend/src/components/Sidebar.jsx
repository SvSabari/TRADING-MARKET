import { NavLink } from "react-router-dom";
import {
  ChartBar, Lightning, Strategy, ChartLine, Wallet, Receipt, TestTube,
  Database, Robot, Plugs, Gear, Pulse, Crosshair
} from "@phosphor-icons/react";

const NAV = [
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
  { to: "/ai", label: "AI Assistant", icon: Robot, testid: "nav-ai" },
  { to: "/brokers", label: "Brokers", icon: Plugs, testid: "nav-brokers" },
  { to: "/settings", label: "Settings", icon: Gear, testid: "nav-settings" },
];

export default function Sidebar() {
  return (
    <div data-testid="sidebar" className="flex flex-col h-full">
      <div className="px-4 py-4 border-b flex items-center gap-2">
        <div className="w-8 h-8 rounded-full flex items-center justify-center shadow-sm" style={{ backgroundColor: 'var(--brand)', color: '#fff', fontFamily: "Outfit", fontWeight: 700, fontSize: 16 }}>T</div>
        <div>
          <div style={{ fontFamily: "Outfit", fontWeight: 700, fontSize: 15, letterSpacing: "-0.01em", color: 'var(--text-primary)' }}>TRADE</div>
          <div className="text-[10px] uppercase tracking-widest mono" style={{ color: 'var(--brand)' }}>trading terminal</div>
        </div>
      </div>
      <nav className="flex-1 py-2">
        {NAV.map((n) => (
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
        <div className="flex items-center gap-2 text-xs mono">
          <span className="dot dot-live"></span>
          <span>NSE · LIVE</span>
        </div>
      </div>
    </div>
  );
}
