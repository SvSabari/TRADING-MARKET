import { LineChart, Line, ResponsiveContainer, YAxis, XAxis, Tooltip } from "recharts";
import { useMemo } from "react";

const TICK = { fill: "#555", fontSize: 10, fontFamily: "JetBrains Mono" };
const X_TICK = { fill: "#555", fontSize: 9, fontFamily: "JetBrains Mono" };
const TOOLTIP_STYLE = { background: "var(--surface)", border: "1px solid var(--border)", fontFamily: "JetBrains Mono", fontSize: 11, color: "var(--text-primary)", borderRadius: 4, boxShadow: "var(--shadow-md)" };

export default function LivePriceChart({ history }) {
  const formatter = useMemo(() => (t) => new Date(t).toLocaleTimeString("en-IN", { hour12: false }).slice(0, 5), []);
  return (
    <div style={{ height: 280 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={history} margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
          <XAxis dataKey="ts" tick={X_TICK} tickFormatter={formatter} stroke="#222" />
          <YAxis domain={["auto", "auto"]} tick={TICK} stroke="#222" />
          <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "#888" }} />
          <Line type="linear" dataKey="ltp" stroke="#00E676" strokeWidth={1.5} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
