import { useMemo } from "react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, LineChart, Line, ComposedChart } from "recharts";

const X_TICK = { fill: "#555", fontSize: 9, fontFamily: "JetBrains Mono" };
const Y_TICK = { fill: "#555", fontSize: 9, fontFamily: "JetBrains Mono" };
const TIP_STYLE = { background: "var(--surface)", border: "1px solid var(--border)", fontFamily: "JetBrains Mono", fontSize: 11, padding: "8px", color: "var(--text-primary)", borderRadius: 4, boxShadow: "var(--shadow-md)" };

const CustomMACDTooltip = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;
  const timeStr = new Date(label).toLocaleTimeString("en-IN", { hour12: false });
  const macd = payload.find(p => p.dataKey === "macd")?.value || 0;
  const signal = payload.find(p => p.dataKey === "signal")?.value || 0;
  const hist = macd - signal;

  return (
    <div style={TIP_STYLE} className="flex flex-col gap-1 rounded shadow-lg">
      <div className="text-gray-500 mb-1">{timeStr}</div>
      <div style={{ color: "#007AFF" }}>MACD: {macd.toFixed(3)}</div>
      <div style={{ color: "#FF9500" }}>Signal: {signal.toFixed(3)}</div>
      <div style={{ color: hist >= 0 ? "#2A9D8F" : "#E76F51" }}>
        Hist: {hist > 0 ? "+" : ""}{hist.toFixed(3)}
      </div>
    </div>
  );
};

export function OIHeatmapChart({ data }) {
  const margin = useMemo(() => ({ top: 10, right: 16, bottom: 0, left: 0 }), []);
  return (
    <div style={{ height: 260 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={margin}>
          <XAxis dataKey="strike" tick={X_TICK} stroke="#E8E0D5" />
          <YAxis tick={Y_TICK} stroke="#E8E0D5" />
          <Tooltip contentStyle={TIP_STYLE} />
          <Bar dataKey="ce_oi" fill="#E76F51" />
          <Bar dataKey="pe_oi" fill="#2A9D8F" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function IVSmileChart({ data }) {
  const margin = useMemo(() => ({ top: 10, right: 16, bottom: 0, left: 0 }), []);
  return (
    <div style={{ height: 260 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={margin}>
          <XAxis dataKey="strike" tick={X_TICK} stroke="#E8E0D5" />
          <YAxis tick={Y_TICK} stroke="#E8E0D5" />
          <Tooltip contentStyle={TIP_STYLE} />
          <Line type="monotone" dataKey="ce_iv" stroke="#E76F51" strokeWidth={1.5} dot={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="pe_iv" stroke="#2A9D8F" strokeWidth={1.5} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function calculateMACD(data, shortPeriod = 12, longPeriod = 26, signalPeriod = 9) {
  if (!data || data.length === 0) return [];
  const calcEMA = (data, period) => {
    const k = 2 / (period + 1);
    let ema = data[0].ltp;
    return data.map((d) => {
      ema = (d.ltp - ema) * k + ema;
      return ema;
    });
  };
  const shortEMA = calcEMA(data, shortPeriod);
  const longEMA = calcEMA(data, longPeriod);
  const macdLine = data.map((d, i) => shortEMA[i] - longEMA[i]);
  const kSignal = 2 / (signalPeriod + 1);
  let signalEma = macdLine[0];
  const signalLine = macdLine.map(m => {
    signalEma = (m - signalEma) * kSignal + signalEma;
    return signalEma;
  });
  return data.map((d, i) => {
    const h = macdLine[i] - signalLine[i];
    return {
      ts: d.ts,
      macd: macdLine[i],
      signal: signalLine[i],
      histPos: h >= 0 ? h : 0,
      histNeg: h < 0 ? h : 0,
    };
  });
}

export function MACDChart({ history }) {
  const margin = useMemo(() => ({ top: 10, right: 16, bottom: 0, left: 0 }), []);
  const formatter = useMemo(() => (t) => new Date(t).toLocaleTimeString("en-IN", { hour12: false }).slice(0, 5), []);
  const macdData = useMemo(() => calculateMACD(history || []), [history]);

  return (
    <div style={{ height: 260 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={macdData} margin={margin}>
          <XAxis dataKey="ts" tick={X_TICK} tickFormatter={formatter} stroke="#E8E0D5" />
          <YAxis tick={Y_TICK} stroke="#E8E0D5" />
          <Tooltip content={<CustomMACDTooltip />} />
          <Bar dataKey="histPos" fill="#2A9D8F" isAnimationActive={false} stackId="a" />
          <Bar dataKey="histNeg" fill="#E76F51" isAnimationActive={false} stackId="a" />
          <Line type="monotone" dataKey="macd" stroke="#007AFF" strokeWidth={1.5} dot={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="signal" stroke="#FF9500" strokeWidth={1.5} dot={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
