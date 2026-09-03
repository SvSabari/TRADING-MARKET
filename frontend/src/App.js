import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/lib/auth-context";
import AppShell from "@/components/AppShell";
import { Toaster } from "sonner";

import Login from "@/pages/Login";
import Register from "@/pages/Register";
import Dashboard from "@/pages/Dashboard";
import Signals from "@/pages/Signals";
import TradingView from "@/pages/TradingView";
import Strategies from "@/pages/Strategies";
import OptionChain from "@/pages/OptionChain";
import PremiumMatcherPage from "@/pages/PremiumMatcherPage";
import Positions from "@/pages/Positions";
import Orders from "@/pages/Orders";
import Backtest from "@/pages/Backtest";
import ParquetData from "@/pages/ParquetData";
import Chart from "@/pages/Chart";
import AI from "@/pages/AI";
import Profile from "@/pages/Profile";
import Brokers from "@/pages/Brokers";
import Settings from "@/pages/Settings";
import Notifications from "@/pages/Notifications";
import UserManagement from "@/pages/UserManagement";
import UserDashboard from "@/pages/UserDashboard";
import MarketHeatmap from "@/pages/MarketHeatmap";

const wrap = (Page) => <AppShell><Page /></AppShell>;

export default function App() {
  return (
    <AuthProvider>
      <Toaster theme="light" position="bottom-right" />
      <BrowserRouter>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Managed User â€” standalone page (no trader shell) */}
          <Route path="/user-dashboard" element={<UserDashboard />} />

          {/* Trader pages â€” wrapped in full AppShell */}
          <Route path="/" element={wrap(Dashboard)} />
          <Route path="/signals" element={wrap(Signals)} />
          <Route path="/tradingview" element={wrap(TradingView)} />
          <Route path="/strategies" element={wrap(Strategies)} />
          <Route path="/option-chain" element={wrap(OptionChain)} />
          <Route path="/premium-matcher" element={wrap(PremiumMatcherPage)} />
          <Route path="/positions" element={wrap(Positions)} />
          <Route path="/orders" element={wrap(Orders)} />
          <Route path="/backtest" element={wrap(Backtest)} />
          <Route path="/parquet" element={wrap(ParquetData)} />
          <Route path="/chart" element={wrap(Chart)} />
          <Route path="/heatmap" element={wrap(MarketHeatmap)} />
          <Route path="/ai" element={wrap(AI)} />
          <Route path="/profile" element={wrap(Profile)} />
          <Route path="/brokers" element={wrap(Brokers)} />
          <Route path="/settings" element={wrap(Settings)} />
          <Route path="/notifications" element={wrap(Notifications)} />
          <Route path="/user-management" element={wrap(UserManagement)} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
