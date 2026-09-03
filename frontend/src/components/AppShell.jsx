import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth-context";
import { Toaster } from "sonner";
import Sidebar from "@/components/Sidebar";
import Topbar from "@/components/Topbar";
import StatusBar from "@/components/StatusBar";
import Ticker from "@/components/Ticker";
import RightSidebar from "@/components/RightSidebar";
import { CaretRight, CaretLeft } from "@phosphor-icons/react";

export default function AppShell({ children }) {
  const { user, loading, isManagedUser } = useAuth();
  const navigate = useNavigate();
  const [rightCollapsed, setRightCollapsed] = useState(false);

  useEffect(() => {
    const hasToken = !!localStorage.getItem("token");
    if (!loading && !user && !hasToken) {
      navigate("/login");
    } else if (!loading && user && isManagedUser) {
      navigate("/user-dashboard");
    }
  }, [loading, user, isManagedUser, navigate]);

  const hasToken = !!localStorage.getItem("token");
  if (loading || (!user && hasToken)) {
    return (
      <div className="h-screen flex items-center justify-center bg-black">
        <div className="num text-sm dim">Loading terminal…</div>
      </div>
    );
  }
  if (!user || isManagedUser) return null;

  return (
    <div className={`app-shell ${rightCollapsed ? 'right-collapsed' : ''}`}>
      <aside className="app-sidebar"><Sidebar /></aside>
      <header className="app-topbar"><Topbar /></header>
      <div className="app-ticker"><Ticker /></div>
      <main className="app-main" data-testid="app-main">
        <div className="p-4 pb-8 h-full w-full flex flex-col overflow-y-auto">
          {children}
        </div>
        <button 
          onClick={() => setRightCollapsed(!rightCollapsed)}
          className="absolute right-0 top-1/2 -translate-y-1/2 z-50 flex items-center justify-center bg-[var(--surface)] border border-[var(--border)] shadow-sm hover:bg-[var(--surface-hover)]"
          style={{ width: '24px', height: '48px', borderRight: 'none', borderRadius: '4px 0 0 4px', cursor: 'pointer' }}
          title={rightCollapsed ? "Expand Quick Order Panel" : "Collapse Quick Order Panel"}
        >
          {rightCollapsed ? <CaretLeft size={16} /> : <CaretRight size={16} />}
        </button>
      </main>
      <aside className="app-right-sidebar"><RightSidebar /></aside>
      <footer className="app-status"><StatusBar /></footer>
      <Toaster theme="light" position="bottom-right" toastOptions={{
        style: { background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)", borderRadius: "2px", fontFamily: "JetBrains Mono, monospace", fontSize: "12px" },
      }} />
    </div>
  );
}
