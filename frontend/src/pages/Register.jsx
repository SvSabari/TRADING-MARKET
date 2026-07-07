import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth-context";
import { Lightning } from "@phosphor-icons/react";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await register(email, name, password);
      toast.success("Account ready. Welcome to Algonid.");
      navigate("/");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Registration failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-8 bg-[#0A0A0A]" data-testid="register-page">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-2">
          <div className="w-7 h-7 bg-[#00E676] flex items-center justify-center" style={{ fontFamily: "Chivo", fontWeight: 900, color: "#000" }}>A</div>
          <div style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 16 }}>ALGONID</div>
        </div>
        <div className="dim text-[10px] mono uppercase tracking-widest mb-2">→ new terminal</div>
        <h2 style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 36, letterSpacing: "-0.02em" }}>Register.</h2>
        <p className="dim text-sm mt-2">Provision a trader account on this instance.</p>

        <form className="mt-8 space-y-4" onSubmit={submit}>
          <div>
            <label className="block dim text-[10px] mono uppercase tracking-widest mb-1">name</label>
            <input className="terminal" data-testid="register-name-input" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div>
            <label className="block dim text-[10px] mono uppercase tracking-widest mb-1">email</label>
            <input className="terminal" type="email" data-testid="register-email-input" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div>
            <label className="block dim text-[10px] mono uppercase tracking-widest mb-1">password (min 6)</label>
            <input className="terminal" type="password" data-testid="register-password-input" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} />
          </div>
          <button className="btn btn-primary w-full justify-center" data-testid="register-submit-btn" disabled={busy}>
            <Lightning size={14} weight="bold" /> {busy ? "Provisioning…" : "Create account"}
          </button>
        </form>
        <div className="mt-6 text-xs dim">
          Already have one? <Link to="/login" data-testid="goto-login-link" className="buy">Sign in →</Link>
        </div>
      </div>
    </div>
  );
}
