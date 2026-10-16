import axios from "axios";

// In production (same-domain or reverse-proxy), fallback to window.location.origin or relative path
const getBackendUrl = () => {
  if (process.env.REACT_APP_BACKEND_URL && !process.env.REACT_APP_BACKEND_URL.includes("your-production-domain")) {
    return process.env.REACT_APP_BACKEND_URL;
  }
  if (typeof window !== "undefined" && window.location.origin) {
    return window.location.origin;
  }
  return "";
};

const BACKEND_URL = getBackendUrl();
export const API = BACKEND_URL ? `${BACKEND_URL}/api` : "/api";
console.log("[frontend] API baseURL:", API);

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem("token");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  console.log("[frontend] api request", cfg.method?.toUpperCase(), cfg.baseURL + cfg.url, cfg.headers);
  return cfg;
});

api.interceptors.response.use(
  (r) => {
    console.log("[frontend] api response", r.config?.url, r.status, r.data);
    return r;
  },
  (e) => {
    console.error("[frontend] api error", e?.config?.url, e?.response?.status, e?.response?.data, e?.message);
    if (e?.response?.status === 401 && window.location.pathname !== "/login") {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(e);
  },
);
