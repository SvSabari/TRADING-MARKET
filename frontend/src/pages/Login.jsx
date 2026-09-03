import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth-context";
import { biometricSignIn, hasSavedCredentials, isBiometricAvailable, saveCredentials } from "@/lib/biometric";
import { Fingerprint, Lightning, UserCircle, ChartLine, ShieldCheck, Eye, EyeSlash } from "@phosphor-icons/react";
const HERO_BG = "https://images.unsplash.com/photo-1642543492481-44e81e3914a7?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjd8MHwxfHNlYXJjaHw0fHxmaW5hbmNpYWwlMjBjaGFydCUyMG1pbmltYWx8ZW58MHx8fHwxNzg4Njk5OTk5fDA&ixlib=rb-4.1.0&q=85";

export default function Login() {
  const { user, loading, login, userLogin, isManagedUser } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState("trader"); // "trader" | "user"

  // Initialized empty so inputs start completely clear (no pre-filled demo values)
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // User login state
  const [phone, setPhone] = useState("");
  const [userPassword, setUserPassword] = useState("");

  const [busy, setBusy] = useState(false);
  const [bio, setBio] = useState({ available: false, hasSaved: false });

  const [showTraderPassword, setShowTraderPassword] = useState(false);
  const [showUserPassword, setShowUserPassword] = useState(false);

  useEffect(() => {
    if (!loading && user) {
      if (isManagedUser) {
        navigate("/user-dashboard");
      } else {
        navigate("/");
      }
    }
  }, [loading, user, isManagedUser, navigate]);

  useEffect(() => {
    (async () => {
      const a = await isBiometricAvailable();
      const b = a.available ? await hasSavedCredentials() : false;
      setBio({ available: a.available, hasSaved: b });
    })();
  }, []);

  const submitTrader = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email, password);
      toast.success("Authenticated");
      if (bio.available && !bio.hasSaved) {
        try {
          await saveCredentials(email, password);
          toast.message("Biometric login enabled", { description: "Next time, sign in with your fingerprint." });
        } catch (err) { console.error("save creds failed", err); }
      }
      navigate("/");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Login failed");
    } finally { setBusy(false); }
  };

  const submitUser = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await userLogin(phone, userPassword);
      toast.success("Welcome! Redirecting to your dashboard…");
      navigate("/user-dashboard");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Login failed");
    } finally { setBusy(false); }
  };

  const handleBiometric = async () => {
    const creds = await biometricSignIn();
    if (!creds) { toast.error("Biometric verification failed"); return; }
    setBusy(true);
    try {
      await login(creds.email, creds.password);
      toast.success("Signed in with biometrics");
      navigate("/");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Saved credentials are no longer valid — sign in manually.");
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen flex" style={{ background: "var(--bg)", color: "var(--text-primary)" }}>
      {/* Hero Left Section — Light Modern Aesthetic */}
      <div className="hidden lg:flex flex-1 relative overflow-hidden" style={{ background: "#F4EFEA", borderRight: "1px solid var(--border)" }}>
        <img src={HERO_BG} alt="" className="absolute inset-0 w-full h-full object-cover opacity-20" />
        <div className="absolute inset-0" style={{ background: "linear-gradient(135deg, rgba(253,251,247,0.92) 0%, rgba(244,239,234,0.75) 100%)" }} />
        
        <div className="relative z-10 p-12 flex flex-col justify-between w-full">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center shadow-sm" style={{ background: "var(--brand)", color: "#FFF", fontFamily: "Outfit", fontWeight: 800, fontSize: 20 }}>T</div>
            <div>
              <div style={{ fontFamily: "Outfit", fontWeight: 800, fontSize: 20, letterSpacing: "-0.02em", color: "var(--text-primary)" }}>TRADE</div>
              <div className="text-[10px] uppercase tracking-widest mono font-bold" style={{ color: "var(--brand)" }}>trading terminal</div>
            </div>
          </div>

          <div className="max-w-xl my-auto py-8">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold mono mb-6" style={{ background: "rgba(194,163,129,0.15)", color: "var(--text-primary)", border: "1px solid var(--border)" }}>
              <ShieldCheck size={14} weight="fill" style={{ color: "var(--buy)" }} />
              INSTITUTIONAL GRADE EXECUTION
            </div>
            
            <h1 style={{ fontFamily: "Outfit", fontWeight: 800, fontSize: "clamp(36px, 4.5vw, 56px)", lineHeight: 1.05, letterSpacing: "-0.03em", color: "var(--text-primary)" }}>
              Smart Algorithmic<br/>Execution For<br/><span style={{ color: "var(--buy)" }}>Modern Traders.</span>
            </h1>

            <p className="mt-6 text-sm leading-relaxed max-w-md" style={{ color: "var(--text-secondary)", fontFamily: "Outfit" }}>
              TradingView webhook integration · Sub-second multi-broker order routing · Parquet tick analytics · Automated sub-account mirroring.
            </p>

            <div className="mt-10 grid grid-cols-3 gap-4 max-w-md">
              {[
                ["56", "SYMBOLS"],
                ["5s", "TICK CAPTURE"],
                ["100%", "DATA REALTIME"],
              ].map(([n, l]) => (
                <div key={l} className="p-4 rounded-lg shadow-sm" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
                  <div className="num text-2xl font-bold" style={{ color: "var(--buy)" }}>{n}</div>
                  <div className="dim text-[10px] mono tracking-widest uppercase mt-1 font-semibold">{l}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="dim text-xs mono tracking-widest uppercase">
            © TRADE TERMINAL · LIVE BROKER CONNECTED
          </div>
        </div>
      </div>

      {/* Login Right Section — Light Theme Card */}
      <div className="flex-1 flex items-center justify-center p-8" style={{ background: "var(--surface)" }} data-testid="login-page">
        <div className="w-full max-w-sm">
          <div className="lg:hidden mb-8 flex items-center gap-2">
            <div className="w-8 h-8 rounded-md flex items-center justify-center" style={{ background: "var(--brand)", color: "#FFF", fontFamily: "Outfit", fontWeight: 800 }}>T</div>
            <div style={{ fontFamily: "Outfit", fontWeight: 800, fontSize: 18 }}>TRADE</div>
          </div>

          <div className="dim text-[10px] mono uppercase tracking-widest mb-1 font-semibold">→ Portal Access</div>
          <h2 style={{ fontFamily: "Outfit", fontWeight: 800, fontSize: 32, letterSpacing: "-0.02em", color: "var(--text-primary)" }}>Sign in.</h2>
          <p className="dim text-xs mt-1">Select your account type to proceed.</p>

          {/* Login Type Switcher Tabs */}
          <div className="mt-6 flex rounded-lg p-1" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
            <button
              type="button"
              onClick={() => setTab("trader")}
              className="flex-1 flex items-center justify-center gap-2 py-2 rounded text-xs font-bold mono uppercase tracking-wider transition-all"
              style={{
                background: tab === "trader" ? "var(--surface)" : "transparent",
                color: tab === "trader" ? "var(--text-primary)" : "var(--text-secondary)",
                boxShadow: tab === "trader" ? "var(--shadow-sm)" : "none",
                border: tab === "trader" ? "1px solid var(--border)" : "1px solid transparent",
              }}
            >
              <ChartLine size={14} weight="bold" style={{ color: tab === "trader" ? "var(--buy)" : "inherit" }} /> Trader
            </button>
            <button
              type="button"
              onClick={() => setTab("user")}
              className="flex-1 flex items-center justify-center gap-2 py-2 rounded text-xs font-bold mono uppercase tracking-wider transition-all"
              style={{
                background: tab === "user" ? "var(--surface)" : "transparent",
                color: tab === "user" ? "var(--text-primary)" : "var(--text-secondary)",
                boxShadow: tab === "user" ? "var(--shadow-sm)" : "none",
                border: tab === "user" ? "1px solid var(--border)" : "1px solid transparent",
              }}
            >
              <UserCircle size={14} weight="bold" style={{ color: tab === "user" ? "var(--buy)" : "inherit" }} /> User
            </button>
          </div>

          {/* Trader Login Form */}
          {tab === "trader" && (
            <form className="mt-6 space-y-4" onSubmit={submitTrader} autoComplete="off">
              <div>
                <label className="block dim text-[10px] mono uppercase tracking-widest mb-1.5 font-semibold">Email Address</label>
                <input
                  className="terminal w-full"
                  type="email"
                  name="trader_email_clean"
                  autoComplete="off"
                  data-testid="login-email-input"
                  placeholder="Enter your email address"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="block dim text-[10px] mono uppercase tracking-widest mb-1.5 font-semibold">Password</label>
                <div className="relative">
                  <input
                    className="terminal w-full pr-10"
                    type={showTraderPassword ? "text" : "password"}
                    name="trader_pass_clean"
                    autoComplete="new-password"
                    data-testid="login-password-input"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowTraderPassword(!showTraderPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 dim hover:text-white transition-colors"
                  >
                    {showTraderPassword ? <EyeSlash size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
              <button
                className="btn btn-primary w-full justify-center py-3 text-xs font-bold mono uppercase tracking-widest mt-2"
                style={{ height: 42 }}
                data-testid="login-submit-btn"
                disabled={busy}
              >
                <Lightning size={14} weight="bold" /> {busy ? "Authenticating…" : "Sign In to Terminal"}
              </button>
              {bio.available && bio.hasSaved && (
                <button
                  type="button"
                  className="btn w-full justify-center py-2.5 text-xs font-bold"
                  data-testid="login-biometric-btn"
                  onClick={handleBiometric}
                  disabled={busy}
                >
                  <Fingerprint size={14} weight="bold" /> Sign in with biometrics
                </button>
              )}
              <div className="mt-4 text-xs dim text-center">
                Need a trader account? <Link to="/register" data-testid="goto-register-link" className="buy font-semibold">Register here →</Link>
              </div>
            </form>
          )}

          {/* User Login Form */}
          {tab === "user" && (
            <form className="mt-6 space-y-4" onSubmit={submitUser} autoComplete="off">
              <div>
                <label className="block dim text-[10px] mono uppercase tracking-widest mb-1.5 font-semibold">Phone Number</label>
                <input
                  className="terminal w-full"
                  type="tel"
                  name="user_phone_clean"
                  autoComplete="off"
                  data-testid="user-login-phone-input"
                  placeholder="Enter your phone number"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="block dim text-[10px] mono uppercase tracking-widest mb-1.5 font-semibold">Password</label>
                <div className="relative">
                  <input
                    className="terminal w-full pr-10"
                    type={showUserPassword ? "text" : "password"}
                    name="user_pass_clean"
                    autoComplete="new-password"
                    data-testid="user-login-password-input"
                    placeholder="Enter your password"
                    value={userPassword}
                    onChange={(e) => setUserPassword(e.target.value)}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowUserPassword(!showUserPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 dim hover:text-white transition-colors"
                  >
                    {showUserPassword ? <EyeSlash size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
              <button
                className="btn btn-primary w-full justify-center py-3 text-xs font-bold mono uppercase tracking-widest mt-2"
                style={{ height: 42 }}
                data-testid="user-login-submit-btn"
                disabled={busy}
              >
                <UserCircle size={14} weight="bold" /> {busy ? "Authenticating…" : "Login to User Portal"}
              </button>
              <p className="dim text-[10px] text-center mono leading-normal mt-3">
                Passwords for user accounts are created by your managing trader.
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
