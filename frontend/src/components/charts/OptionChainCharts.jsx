import { useMemo } from "react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, LineChart, Line } from "recharts";

const X_TICK = { fill: "#555", fontSize: 9, fontFamily: "JetBrains Mono" };
const Y_TICK = { fill: "#555", fontSize: 9, fontFamily: "JetBrains Mono" };
const TIP_STYLE = { background: "#0A0A0A", border: "1px solid #222", fontFamily: "JetBrains Mono", fontSize: 11 };

export function OIHeatmapChart({ data }) {
  const margin = useMemo(() => ({ top: 10, right: 16, bottom: 0, left: 0 }), []);
  return (
    <div style={{ height: 260 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={margin}>
          <XAxis dataKey="strike" tick={X_TICK} stroke="#222" />
          <YAxis tick={Y_TICK} stroke="#222" />
          <Tooltip contentStyle={TIP_STYLE} />
          <Bar dataKey="ce_oi" fill="#FF3B30" />
          <Bar dataKey="pe_oi" fill="#00E676" />
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
          <XAxis dataKey="strike" tick={X_TICK} stroke="#222" />
          <YAxis tick={Y_TICK} stroke="#222" />
          <Tooltip contentStyle={TIP_STYLE} />
          <Line type="monotone" dataKey="ce_iv" stroke="#FF3B30" strokeWidth={1.5} dot={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="pe_iv" stroke="#00E676" strokeWidth={1.5} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
