import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth-context";
import { biometricSignIn, hasSavedCredentials, isBiometricAvailable, saveCredentials } from "@/lib/biometric";
import { Fingerprint, Lightning } from "@phosphor-icons/react";

const HERO_BG = "https://images.unsplash.com/photo-1762279389083-abf71f22d338?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjd8MHwxfHNlYXJjaHwyfHxmaW5hbmNpYWwlMjBjaGFydCUyMG5lb24lMjBhYnN0cmFjdHxlbnwwfHx8fDE3ODA5ODI1MzJ8MA&ixlib=rb-4.1.0&q=85";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("demo@trader.io");
  const [password, setPassword] = useState("demo123");
  const [busy, setBusy] = useState(false);
  const [bio, setBio] = useState({ available: false, hasSaved: false });

  useEffect(() => {
    (async () => {
      const a = await isBiometricAvailable();
      const b = a.available ? await hasSavedCredentials() : false;
      setBio({ available: a.available, hasSaved: b });
    })();
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email, password);
      toast.success("Authenticated");
      // offer to save credentials for biometric on native
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
    <div className="min-h-screen flex">
      <div className="hidden lg:flex flex-1 relative" style={{ background: "#000" }}>
        <img src={HERO_BG} alt="" className="absolute inset-0 w-full h-full object-cover opacity-60" />
        <div className="absolute inset-0" style={{ background: "linear-gradient(120deg, rgba(0,0,0,0.95), rgba(0,0,0,0.55))" }} />
        <div className="relative z-10 p-12 flex flex-col justify-between w-full">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-[#00E676] flex items-center justify-center" style={{ fontFamily: "Chivo", fontWeight: 900, color: "#000", fontSize: 18 }}>A</div>
            <div>
              <div style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 18, letterSpacing: "-0.02em" }}>ALGONID</div>
              <div className="dim text-xs mono tracking-widest">TRADING TERMINAL · v0.1</div>
            </div>
          </div>
          <div>
            <h1 style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: "clamp(40px, 5vw, 64px)", lineHeight: 0.95, letterSpacing: "-0.03em" }}>
              ALGORITHMIC<br/>EXECUTION FOR<br/><span className="buy">RETAIL TRADERS.</span>
            </h1>
            <p className="dim mt-6 max-w-md" style={{ fontFamily: "IBM Plex Sans" }}>
              TradingView webhook execution · All Symbols 5-second volume capture to Parquet ·
              Broker-agnostic order routing · Claude-powered trade explainer.
            </p>
            <div className="mt-8 grid grid-cols-3 gap-px bg-[#222] max-w-md">
              {[
                ["56", "SYMBOLS"],
                ["5s", "TICK CAPTURE"],
                ["∞", "PARQUET ROWS"],
              ].map(([n, l]) => (
                <div key={l} className="bg-black p-4">
                  <div className="num text-2xl buy">{n}</div>
                  <div className="dim text-[10px] mono tracking-widest uppercase mt-1">{l}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="dim text-xs mono tracking-widest">© ALGONID · NSE/BSE · PAPER-TRADE READY</div>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center p-8 bg-[#0A0A0A]" data-testid="login-page">
        <div className="w-full max-w-sm">
          <div className="lg:hidden mb-8 flex items-center gap-2">
            <div className="w-7 h-7 bg-[#00E676] flex items-center justify-center" style={{ fontFamily: "Chivo", fontWeight: 900, color: "#000" }}>A</div>
            <div style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 16 }}>ALGONID</div>
          </div>
          <div className="dim text-[10px] mono uppercase tracking-widest mb-2">→ access terminal</div>
          <h2 style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 36, letterSpacing: "-0.02em" }}>Sign in.</h2>
          <p className="dim text-sm mt-2">Use the demo account or register your own.</p>

          <form className="mt-8 space-y-4" onSubmit={submit}>
            <div>
              <label className="block dim text-[10px] mono uppercase tracking-widest mb-1">email</label>
              <input className="terminal" data-testid="login-email-input" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div>
              <label className="block dim text-[10px] mono uppercase tracking-widest mb-1">password</label>
              <input className="terminal" type="password" data-testid="login-password-input" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <button className="btn btn-primary w-full justify-center" data-testid="login-submit-btn" disabled={busy}>
              <Lightning size={14} weight="bold" /> {busy ? "Authenticating…" : "Engage"}
            </button>
            {bio.available && bio.hasSaved && (
              <button type="button" className="btn w-full justify-center" data-testid="login-biometric-btn" onClick={handleBiometric} disabled={busy}>
                <Fingerprint size={14} weight="bold" /> Sign in with biometrics
              </button>
            )}
          </form>
          <div className="mt-6 text-xs dim">
            No account? <Link to="/register" data-testid="goto-register-link" className="buy">Create one →</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
