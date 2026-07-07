import { useState } from "react";
import { ArrowSquareOut } from "@phosphor-icons/react";
import Panel from "@/components/Panel";
import BrokerForm from "@/components/brokers/BrokerForm";
import ConnectionsTable from "@/components/brokers/ConnectionsTable";
import { useBrokerManagement } from "@/components/brokers/useBrokerManagement";

export default function Brokers() {
  const { conns, schemas, save, remove, connectKite, disconnectKite, connectAngel, connectUpstox } = useBrokerManagement();
  const [selected, setSelected] = useState("zerodha");
  const [values, setValues] = useState({});
  const [mockMode, setMockMode] = useState(true);

  const schema = { id: selected, ...(schemas[selected] || { fields: [] }) };

  const handleSave = async () => {
    await save(selected, values, mockMode, schema.name);
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

  const upstoxExtras = selected === "upstox" ? (
    <button className="btn" onClick={connectUpstox} data-testid="upstox-connect-btn">
      <ArrowSquareOut size={14} weight="bold" /> Complete Upstox OAuth
    </button>
  ) : null;

  const angelExtras = selected === "angel" ? (
    <button className="btn" onClick={connectAngel} data-testid="angel-connect-btn">
      <ArrowSquareOut size={14} weight="bold" /> Generate Angel session (TOTP)
    </button>
  ) : null;

  const extras = zerodhaExtras || upstoxExtras || angelExtras;

  return (
    <div className="space-y-4" data-testid="brokers-page">
      <div>
        <h1 style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 28, letterSpacing: "-0.02em" }}>Broker connections.</h1>
        <p className="dim text-sm mt-1">Pick a broker. The form adapts to whatever creds that broker needs. Mock mode routes every order to the in-app paper broker.</p>
      </div>

      <Panel title="Add / update broker" kicker={schema.name || ""}>
        <div className="p-4 flex flex-wrap gap-2" data-testid="broker-tabs">
          {Object.entries(schemas).map(([key, s]) => (
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
          onSave={handleSave}
          extras={extras}
        />
      </Panel>

      <ConnectionsTable conns={conns} schemas={schemas} onRemove={remove} />
    </div>
  );
}
