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
    const isDataFeed = accountType === "primary";
    const isOrderExec = accountType === "secondary";
    await save(selected, values, mockMode, schema.name, isDataFeed, isOrderExec);
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

      <div className="flex gap-2">
        <button 
          className={`px-4 py-2 text-sm font-semibold rounded-t-lg border-b-2 transition-colors ${accountType === "primary" ? "border-[var(--brand)] text-[var(--brand)] bg-[var(--surface)]" : "border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50"}`}
          onClick={() => setAccountType("primary")}
        >
          Primary Account (Live Data)
        </button>
        <button 
          className={`px-4 py-2 text-sm font-semibold rounded-t-lg border-b-2 transition-colors ${accountType === "secondary" ? "border-[var(--brand)] text-[var(--brand)] bg-[var(--surface)]" : "border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50"}`}
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
