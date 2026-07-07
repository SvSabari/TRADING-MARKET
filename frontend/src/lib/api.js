import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "https://api.your-production-domain.com";
export const API = `${BACKEND_URL}/api`;
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
