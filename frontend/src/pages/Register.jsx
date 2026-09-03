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
    <div className="min-h-screen flex items-center justify-center p-8" style={{ background: "var(--surface)", color: "var(--text-primary)" }} data-testid="register-page">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-2">
          <div className="w-8 h-8 rounded-md flex items-center justify-center" style={{ background: "var(--brand)", color: "#FFF", fontFamily: "Outfit", fontWeight: 800 }}>T</div>
          <div style={{ fontFamily: "Outfit", fontWeight: 800, fontSize: 18 }}>TRADE</div>
        </div>
        
        <div className="text-[10px] mono uppercase tracking-widest mb-2 font-bold" style={{ color: "var(--text-tertiary)" }}>+ PORTAL ACCESS</div>
        <h2 style={{ fontFamily: "Outfit", fontWeight: 800, fontSize: 32, letterSpacing: "-0.02em" }}>Register.</h2>
        <p className="text-sm mt-2 font-medium" style={{ color: "var(--text-secondary)" }}>Create a new trader account to access the terminal.</p>

        <form className="mt-8 space-y-5" onSubmit={submit}>
          <div>
            <label className="block text-[10px] mono uppercase tracking-widest mb-2 font-bold" style={{ color: "var(--text-tertiary)" }}>FULL NAME</label>
            <input className="w-full px-4 py-3 rounded-lg text-sm font-medium focus:outline-none focus:ring-1 transition-all" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)", outlineColor: "var(--brand)" }} value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div>
            <label className="block text-[10px] mono uppercase tracking-widest mb-2 font-bold" style={{ color: "var(--text-tertiary)" }}>EMAIL ADDRESS</label>
            <input className="w-full px-4 py-3 rounded-lg text-sm font-medium focus:outline-none focus:ring-1 transition-all" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)", outlineColor: "var(--brand)" }} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div>
            <label className="block text-[10px] mono uppercase tracking-widest mb-2 font-bold" style={{ color: "var(--text-tertiary)" }}>PASSWORD</label>
            <input className="w-full px-4 py-3 rounded-lg text-sm font-medium focus:outline-none focus:ring-1 transition-all" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)", outlineColor: "var(--brand)" }} type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} />
          </div>
          <button className="w-full py-3 rounded-lg text-xs font-bold mono uppercase tracking-widest flex items-center justify-center gap-2 transition-opacity hover:opacity-90" style={{ background: "var(--brand)", color: "#FFF" }} disabled={busy}>
            <UserCircle size={16} weight="bold" /> {busy ? "CREATING..." : "CREATE ACCOUNT"}
          </button>
        </form>
        <div className="mt-6 text-xs text-center font-medium" style={{ color: "var(--text-secondary)" }}>
          Already have an account? <Link to="/login" className="font-bold hover:underline" style={{ color: "var(--brand)" }}>Sign in here &rarr;</Link>
        </div>
      </div>
    </div>
  );
}
