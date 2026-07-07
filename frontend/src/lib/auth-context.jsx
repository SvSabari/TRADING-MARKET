import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const t = localStorage.getItem("token");
    if (!t) { setLoading(false); return; }
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get("/auth/me");
        if (!cancelled) setUser(data);
      } catch (e) {
        console.error("auth /me failed:", e);
        localStorage.removeItem("token");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const login = async (email, password) => {
    try {
      console.log("[frontend] auth login attempt", email);
      const { data } = await api.post("/auth/login", { email, password });
      console.log("[frontend] auth login success", data);
      localStorage.setItem("token", data.access_token);
      setUser(data.user);
      return data.user;
    } catch (error) {
      console.error("[frontend] auth login failed", error);
      throw error;
    }
  };

  const register = async (email, name, password) => {
    const { data } = await api.post("/auth/register", { email, name, password });
    localStorage.setItem("token", data.access_token);
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch (e) {
      console.error("logout failed:", e);
    }
    try {
      const { clearBiometricCredentials } = await import("@/lib/biometric");
      await clearBiometricCredentials();
    } catch (e) { console.error("biometric clear failed:", e); }
    localStorage.removeItem("token");
    setUser(null);
    window.location.href = "/login";
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
