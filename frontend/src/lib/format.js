export const fmtNum = (n, d = 2) => {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
};

export const fmtInt = (n) => {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("en-IN");
};

export const fmtPct = (n, d = 2) => `${n >= 0 ? "+" : ""}${fmtNum(n, d)}%`;

export const fmtRupee = (n, d = 2) => `₹${fmtNum(n, d)}`;

export const fmtBytes = (b) => {
  if (b === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(b) / Math.log(k));
  return `${(b / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
};

export const sideColor = (side) => (side?.toUpperCase() === "BUY" ? "#00E676" : "#FF3B30");

export const fmtTime = (s) => {
  if (!s) return "—";
  const d = new Date(s);
  return d.toLocaleTimeString("en-IN", { hour12: false });
};

export const fmtDateTime = (s) => {
  if (!s) return "—";
  const d = new Date(s);
  return d.toLocaleString("en-IN", { hour12: false });
};
