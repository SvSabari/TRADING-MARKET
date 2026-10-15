import { useState } from "react";
import { ArrowSquareOut } from "@phosphor-icons/react";
import Panel from "@/components/Panel";
import BrokerForm from "@/components/brokers/BrokerForm";
import ConnectionsTable from "@/components/brokers/ConnectionsTable";
import { useBrokerManagement } from "@/components/brokers/useBrokerManagement";

export default function Brokers() {
  const { conns, schemas, save, setMode, remove, connectKite, disconnectKite, connectAliceblue } = useBrokerManagement();
  const [selected, setSelected] = useState("zerodha");
  const [values, setValues] = useState({});
  const [mockMode, setMockMode] = useState(true);
  const [accountType, setAccountType] = useState("primary");

  const schema = { id: selected, ...(schemas[selected] || { fields: [] }) };

  const handleSave = async () => {
    await save(selected, values, mockMode, schema.name, null, null);
    setValues({});
  };

  const zerodhaExtras = selected === "zerodha" ? (
    <>
      <button className="btn" onClick={connectKite} data-testid="kite-connect-btn">
        <ArrowSquareOut size={14} weight="bold" /> Complete Zerodha OAuth
      </button>
      <button className="btn btn-danger" onClick={disconnectKite} data-testid="kite-disconnect-btn">
        Clear Kite session
      </button>
    </>
  ) : null;

  const aliceblueExtras = selected === "aliceblue" ? (
    <>
      <button className="btn" onClick={connectAliceblue} data-testid="aliceblue-connect-btn">
        <ArrowSquareOut size={14} weight="bold" /> Complete Alice Blue OAuth
      </button>
    </>
  ) : null;

  const extras = zerodhaExtras || aliceblueExtras;

  return (
    <div className="space-y-4" data-testid="brokers-page">
      <div>
        <h1 style={{ fontFamily: "Outfit", fontWeight: 700, fontSize: 28, letterSpacing: "-0.02em" }}>Broker connections.</h1>
        <p className="dim text-sm mt-1">Configure your primary and secondary accounts to separate live data from order execution.</p>
      </div>

      {conns.some((c) => c.is_data_feed && (!c.connected || c.session_status !== "active")) && (
        <div className="p-3.5 bg-rose-500/10 border border-rose-500/30 rounded-lg flex items-center justify-between gap-4 text-xs animate-fadeIn">
          <div className="flex items-center gap-2.5">
            <span className="text-lg">⚠️</span>
            <div>
              <div className="text-rose-400 font-bold uppercase tracking-wider text-[11px]">
                Broker Error: Session Not Generated
              </div>
              <div className="text-[#E0E6F0] text-[12px] mt-0.5">
                Daily session is not active for Primary Data Feed (<strong>{schemas[conns.find((c) => c.is_data_feed)?.broker]?.name || conns.find((c) => c.is_data_feed)?.broker?.toUpperCase()}</strong>). Live tick data feed will remain offline until reconnected.
              </div>
            </div>
          </div>
          <button
            className="btn btn-primary whitespace-nowrap py-1.5 px-3 text-xs font-bold"
            onClick={() => {
              const p = conns.find((c) => c.is_data_feed);
              if (p?.broker === "aliceblue") connectAliceblue();
              else if (p?.broker === "zerodha") connectKite();
            }}
          >
            Reconnect Now
          </button>
        </div>
      )}

      <div className="flex gap-2">
        <button 
          className={`px-4 py-2 text-sm font-semibold rounded-t-lg border-b-2 transition-colors ${accountType === "primary" ? "border-[var(--brand)] text-[#60A5FA] bg-[var(--surface)]" : "border-transparent text-[#BAC0D0] hover:text-white hover:bg-[rgba(255,255,255,0.05)]"}`}
          onClick={() => setAccountType("primary")}
        >
          Primary Account (Live Data)
        </button>
        <button 
          className={`px-4 py-2 text-sm font-semibold rounded-t-lg border-b-2 transition-colors ${accountType === "secondary" ? "border-[var(--brand)] text-[#60A5FA] bg-[var(--surface)]" : "border-transparent text-[#BAC0D0] hover:text-white hover:bg-[rgba(255,255,255,0.05)]"}`}
          onClick={() => setAccountType("secondary")}
        >
          Secondary Account (Order Execution)
        </button>
      </div>

      <Panel title={`Add / update ${accountType} broker`} kicker={schema.name || ""}>
        <div className="p-4 flex flex-wrap gap-2" data-testid="broker-tabs">
          {Object.entries(schemas)
            .filter(([key]) => accountType === "secondary" || key !== "mock")
            .map(([key, s]) => (
            <button
              key={key}
              className={`btn ${selected === key ? "btn-primary" : ""}`}
              onClick={() => { setSelected(key); setValues({}); }}
              data-testid={`broker-tab-${key}`}
            >
              {s.name || key}
            </button>
          ))}
        </div>
        <BrokerForm
          schema={schema}
          values={values}
          onChange={setValues}
          mockMode={mockMode}
          onMockChange={setMockMode}
          accountType={accountType}
          onSave={handleSave}
          extras={extras}
        />
      </Panel>

      <ConnectionsTable conns={conns} schemas={schemas} onSetMode={setMode} onRemove={remove} onReconnectAliceblue={connectAliceblue} />
    </div>
  );
}
