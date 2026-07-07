import { Plugs, PlugsConnected, Trash } from "@phosphor-icons/react";

export default function ConnectionsTable({ conns, schemas, onRemove }) {
  return (
    <div className="panel" data-testid="connections-panel">
      <div className="panel-h"><span>Connections</span><span className="kicker">· {conns.length} configured</span></div>
      <table className="w-full text-xs">
        <thead><tr className="dim text-[10px] uppercase tracking-widest border-b border-[#222]">
          <th className="text-left py-2 px-4">Broker</th>
          <th className="text-left py-2 px-4">Status</th>
          <th className="text-left py-2 px-4">Mode</th>
          <th className="text-left py-2 px-4">Fields saved</th>
          <th className="text-left py-2 px-4">Session</th>
          <th className="text-right py-2 px-4">Actions</th>
        </tr></thead>
        <tbody className="cell-divider">
          {conns.map((c) => (
            <tr key={c.id} data-testid={`broker-row-${c.broker}`}>
              <td className="py-2 px-4 mono">{schemas[c.broker]?.name || c.broker}</td>
              <td className={`py-2 px-4 mono ${c.connected ? "buy" : "sell"}`}>
                {c.connected ? <><PlugsConnected size={12} weight="bold" className="inline mr-1" /> CONNECTED</> : <><Plugs size={12} weight="bold" className="inline mr-1" /> DISCONNECTED</>}
              </td>
              <td className="py-2 px-4 mono dim">{c.mock_mode ? "MOCK" : "LIVE"}</td>
              <td className="py-2 px-4 mono dim">{(c.fields_filled || []).join(", ") || "—"}</td>
              <td className="py-2 px-4 mono dim">{c.has_access_token ? c.session_date : "—"}</td>
              <td className="py-2 px-4 text-right">
                <button className="btn btn-danger" onClick={() => onRemove(c.broker)} data-testid={`broker-remove-${c.broker}`}>
                  <Trash size={14} weight="bold" />
                </button>
              </td>
            </tr>
          ))}
          {conns.length === 0 && <tr><td colSpan={6} className="p-8 text-center dim text-xs">No brokers configured. Add one above.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
