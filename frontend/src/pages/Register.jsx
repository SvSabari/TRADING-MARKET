import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth-context";
import { UserCircle } from "@phosphor-icons/react";

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
      toast.success("Account ready. Welcome.");
      navigate("/");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Registration failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 sm:p-8" style={{ background: "var(--bg)", color: "var(--text-primary)" }} data-testid="register-page">
      <div className="w-full max-w-md p-8 sm:p-10 rounded-2xl shadow-xl border relative" style={{ background: "var(--surface)", borderColor: "var(--border)" }}>
        <div className="mb-8 flex flex-col items-center justify-center gap-3">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center shadow-md" style={{ background: "var(--brand)", color: "#FFF", fontFamily: "Outfit", fontWeight: 800, fontSize: 24 }}>T</div>
          <div className="text-center">
            <div style={{ fontFamily: "Outfit", fontWeight: 800, fontSize: 22, letterSpacing: "-0.02em" }}>TRADE<span style={{color: "var(--brand)"}}>RS PRO</span></div>
            <div className="dim text-[10px] mono uppercase tracking-widest mt-1 font-semibold">Portal Access</div>
          </div>
        </div>
        
        <div className="text-center mb-6">
          <h2 style={{ fontFamily: "Outfit", fontWeight: 800, fontSize: 28, letterSpacing: "-0.02em", color: "var(--text-primary)" }}>Create Account</h2>
          <p className="dim text-xs mt-1">Register a new trader account on the terminal</p>
        </div>

        <form className="space-y-4" onSubmit={submit} autoComplete="off">
          <div>
            <label className="block dim text-[10px] mono uppercase tracking-widest mb-1.5 font-semibold">FULL NAME</label>
            <input className="terminal w-full" placeholder="Enter your full name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div>
            <label className="block dim text-[10px] mono uppercase tracking-widest mb-1.5 font-semibold">EMAIL ADDRESS</label>
            <input className="terminal w-full" type="email" placeholder="Enter your email address" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div>
            <label className="block dim text-[10px] mono uppercase tracking-widest mb-1.5 font-semibold">PASSWORD</label>
            <input className="terminal w-full" type="password" placeholder="Create a password (min 6 characters)" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} />
          </div>
          <button className="btn btn-primary w-full py-3 rounded-lg text-xs font-bold mono uppercase tracking-widest flex items-center justify-center gap-2 mt-2" disabled={busy}>
            <UserCircle size={16} weight="bold" /> {busy ? "CREATING..." : "CREATE ACCOUNT"}
          </button>
        </form>
        <div className="mt-6 text-xs text-center font-medium dim">
          Already have an account? <Link to="/login" className="font-bold hover:underline" style={{ color: "var(--brand)" }}>Sign in here &rarr;</Link>
        </div>
      </div>
    </div>
  );
}
