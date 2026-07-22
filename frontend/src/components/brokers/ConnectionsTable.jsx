import { Plugs, PlugsConnected, Trash, ArrowsClockwise } from "@phosphor-icons/react";

export default function ConnectionsTable({ conns, schemas, onSetMode, onRemove, onReconnectAliceblue }) {
  return (
    <div className="panel" data-testid="connections-panel">
      <div className="panel-h"><span>Connections</span><span className="kicker">· {conns.length} configured</span></div>
      <div className="overflow-x-auto">
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
              <td className="py-2 px-4 mono dim">
                <div className="flex gap-2">
                  {c.is_data_feed && <span className="bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded text-[10px] font-bold">PRIMARY ACCOUNT</span>}
                  {c.is_order_exec && (
                    <>
                      <span className="bg-purple-100 text-purple-800 px-1.5 py-0.5 rounded text-[10px] font-bold">SECONDARY ACCOUNT</span>
                      <span className={c.mock_mode ? "bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded text-[10px] font-bold" : "bg-green-100 text-green-800 px-1.5 py-0.5 rounded text-[10px] font-bold"}>
                        {c.mock_mode ? "MOCK" : "LIVE"}
                      </span>
                    </>
                  )}
                  {!c.is_data_feed && !c.is_order_exec && <span>—</span>}
                </div>
              </td>
              <td className="py-2 px-4 mono dim">{(c.fields_filled || []).join(", ") || "—"}</td>
              <td className="py-2 px-4 mono dim">{c.has_access_token ? c.session_date : "—"}</td>
              <td className="py-2 px-4 text-right">
                <div className="flex justify-end gap-2">
                  {c.broker === "aliceblue" && (
                    <button className="btn whitespace-nowrap" title="Refresh Session Token" onClick={onReconnectAliceblue} data-testid={`broker-reconnect-${c.broker}`}>
                      <ArrowsClockwise size={14} weight="bold" className="inline" /> Reconnect
                    </button>
                  )}
                  <button
                    className={`btn whitespace-nowrap ${c.is_data_feed ? "border-blue-500 bg-blue-500/10 text-blue-600 cursor-default opacity-80" : "btn-outline"}`}
                    title={c.is_data_feed ? "Currently used for Live Data" : "Set as Primary Account (Live Data)"}
                    onClick={() => !c.is_data_feed && onSetMode(c, true, c.is_order_exec)}
                  >
                    {c.is_data_feed ? "Primary ✓" : "Set Primary"}
                  </button>
                  <button
                    className={`btn whitespace-nowrap ${c.is_order_exec ? "border-purple-500 bg-purple-500/10 text-purple-600 cursor-default opacity-80" : "btn-outline"}`}
                    title={c.is_order_exec ? "Currently used for Orders" : "Set as Secondary Account (Orders)"}
                    onClick={() => !c.is_order_exec && onSetMode(c, c.is_data_feed, true)}
                  >
                    {c.is_order_exec ? "Secondary ✓" : "Set Secondary"}
                  </button>
                  <button className="btn btn-danger" title="Delete connection" onClick={() => onRemove(c.broker)} data-testid={`broker-remove-${c.broker}`}>
                    <Trash size={14} weight="bold" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
          {conns.length === 0 && <tr><td colSpan={6} className="p-8 text-center dim text-xs">No brokers configured. Add one above.</td></tr>}
        </tbody>
      </table>
      </div>
    </div>
  );
}
