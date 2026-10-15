import { Plugs, PlugsConnected, Trash, ArrowsClockwise } from "@phosphor-icons/react";

export default function ConnectionsTable({ conns, schemas, onSetMode, onRemove, onReconnectAliceblue }) {
  return (
    <div className="panel" data-testid="connections-panel">
      <div className="panel-h"><span>Connections</span><span className="kicker">· {conns.length} configured</span></div>
      <div className="w-full overflow-hidden">
        <table className="w-full text-xs">
        <thead><tr className="dim text-[10px] uppercase tracking-widest border-b border-[#222]">
          <th className="text-left py-2 px-3">Broker</th>
          <th className="text-left py-2 px-3">Status</th>
          <th className="text-left py-2 px-3">Mode</th>
          <th className="text-left py-2 px-3">Fields saved</th>
          <th className="text-left py-2 px-3">Session</th>
          <th className="text-right py-2 px-3">Actions</th>
        </tr></thead>
        <tbody className="cell-divider">
          {conns.map((c) => (
            <tr key={c.id} data-testid={`broker-row-${c.broker}`}>
              <td className="py-2 px-3 mono whitespace-nowrap">{schemas[c.broker]?.name || c.broker}</td>
              <td className={`py-2 px-3 mono whitespace-nowrap ${c.connected ? "buy font-bold" : "sell font-bold"}`}>
                {c.connected ? <><PlugsConnected size={12} weight="bold" className="inline mr-1" /> CONNECTED</> : <><Plugs size={12} weight="bold" className="inline mr-1" /> DISCONNECTED</>}
              </td>
              <td className="py-2 px-3 mono dim">
                <div className="flex flex-col gap-1 items-start">
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
              <td className="py-2 px-3 mono dim text-[11px]">{(c.fields_filled || []).join(", ") || "—"}</td>
              <td className="py-2 px-3 mono dim whitespace-nowrap">
                {c.has_access_token ? c.session_date : (c.connected ? "Active" : "—")}
              </td>
              <td className="py-2 px-3 text-right">
                <div className="flex justify-end gap-1.5 whitespace-nowrap">
                  {c.broker === "aliceblue" && (
                    <button className="btn btn-sm px-2.5 py-1 text-[11px] whitespace-nowrap" title="Refresh Session Token" onClick={onReconnectAliceblue} data-testid={`broker-reconnect-${c.broker}`}>
                      <ArrowsClockwise size={13} weight="bold" className="inline mr-0.5" /> Reconnect
                    </button>
                  )}
                  <button
                    className={`btn btn-sm px-2.5 py-1 text-[11px] whitespace-nowrap ${c.is_data_feed ? "border-blue-500 bg-blue-500/10 text-blue-400 cursor-default" : "btn-outline"}`}
                    title={c.is_data_feed ? "Currently used for Live Data" : "Set as Primary Account (Live Data)"}
                    onClick={() => !c.is_data_feed && onSetMode(c, true, c.is_order_exec)}
                  >
                    {c.is_data_feed ? "Primary ✓" : "Set Primary"}
                  </button>
                  <button
                    className={`btn btn-sm px-2.5 py-1 text-[11px] whitespace-nowrap ${c.is_order_exec ? "border-purple-500 bg-purple-500/10 text-purple-400 cursor-default" : "btn-outline"}`}
                    title={c.is_order_exec ? "Currently used for Orders" : "Set as Secondary Account (Orders)"}
                    onClick={() => !c.is_order_exec && onSetMode(c, c.is_data_feed, true)}
                  >
                    {c.is_order_exec ? "Secondary ✓" : "Set Secondary"}
                  </button>
                  <button className="btn btn-sm btn-danger px-2 py-1 text-[11px]" title="Delete connection" onClick={() => onRemove(c.broker)} data-testid={`broker-remove-${c.broker}`}>
                    <Trash size={13} weight="bold" />
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
