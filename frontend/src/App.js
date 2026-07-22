import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/lib/auth-context";
import AppShell from "@/components/AppShell";

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
import AI from "@/pages/AI";
import Brokers from "@/pages/Brokers";
import Settings from "@/pages/Settings";
import Notifications from "@/pages/Notifications";

const wrap = (Page) => <AppShell><Page /></AppShell>;

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
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
          <Route path="/ai" element={wrap(AI)} />
          <Route path="/brokers" element={wrap(Brokers)} />
          <Route path="/settings" element={wrap(Settings)} />
          <Route path="/notifications" element={wrap(Notifications)} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
