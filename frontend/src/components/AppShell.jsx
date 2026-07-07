import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth-context";
import { Toaster } from "sonner";
import Sidebar from "@/components/Sidebar";
import Topbar from "@/components/Topbar";
import StatusBar from "@/components/StatusBar";
import Ticker from "@/components/Ticker";
import RightSidebar from "@/components/RightSidebar";

export default function AppShell({ children }) {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  useEffect(() => {
    if (!loading && !user) navigate("/login");
  }, [loading, user, navigate]);

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-black">
        <div className="num text-sm dim">Loading terminal…</div>
      </div>
    );
  }
  if (!user) return null;

  return (
    <div className="app-shell">
      <aside className="app-sidebar"><Sidebar /></aside>
      <header className="app-topbar"><Topbar /></header>
      <div className="app-ticker"><Ticker /></div>
      <main className="app-main" data-testid="app-main">{children}</main>
      <aside className="app-right-sidebar"><RightSidebar /></aside>
      <footer className="app-status"><StatusBar /></footer>
      <Toaster theme="dark" position="bottom-right" toastOptions={{
        style: { background: "#121212", border: "1px solid #222", color: "#EDEDED", borderRadius: "2px", fontFamily: "JetBrains Mono, monospace", fontSize: "12px" },
      }} />
    </div>
  );
}
