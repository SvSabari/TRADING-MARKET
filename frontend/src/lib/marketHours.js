/**
 * NSE Market Hours utility (IST = UTC+5:30)
 * Regular session: Mon–Fri, 09:15 – 15:30 IST
 * Pre-open:        09:00 – 09:15 IST
 */

export function getMarketStatus() {
  const now = new Date();
  // Convert to IST
  const istOffset = 5.5 * 60; // minutes
  const utcMin = now.getUTCHours() * 60 + now.getUTCMinutes();
  const istMin = (utcMin + istOffset) % (24 * 60);
  const day = (now.getUTCDay() + (utcMin + istOffset >= 24 * 60 ? 1 : 0)) % 7; // 0=Sun,6=Sat

  const isWeekend = day === 0 || day === 6;

  const PREOPEN_START = 9 * 60;       // 9:00 IST
  const MARKET_OPEN  = 9 * 60 + 15;  // 9:15 IST
  const MARKET_CLOSE = 15 * 60 + 30; // 15:30 IST
  const POST_CLOSE   = 16 * 60;      // 16:00 IST

  if (isWeekend) {
    return { open: false, label: "WEEKEND", color: "#aaa" };
  }
  if (istMin < PREOPEN_START) {
    return { open: false, label: "PRE-MARKET", color: "#F59E0B" };
  }
  if (istMin < MARKET_OPEN) {
    return { open: false, label: "PRE-OPEN", color: "#F59E0B" };
  }
  if (istMin < MARKET_CLOSE) {
    return { open: true, label: "LIVE", color: "#00C853" };
  }
  if (istMin < POST_CLOSE) {
    return { open: false, label: "CLOSING", color: "#F59E0B" };
  }
  return { open: false, label: "CLOSED", color: "#EF4444" };
}

export function isMarketOpen() {
  return getMarketStatus().open;
}
