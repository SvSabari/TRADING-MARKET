/* eslint-disable */
export default function BrokerForm({ schema, values, onChange, mockMode, onMockChange, accountType, onSave, extras }) {
  return (
    <div className="p-4 space-y-4">
      {schema.docs && (
        <div className="dim text-xs">
          Docs: <a className="buy mono" href={schema.docs} target="_blank" rel="noreferrer">{schema.docs}</a>
        </div>
      )}
      {schema.redirect_required && (
        <div className="text-xs warn">
          Redirect-based OAuth. Set the Redirect URL in your broker portal to:&nbsp;
          <span className="mono">{window.location.origin}/api/brokers/{schema.id}/callback</span>
        </div>
      )}
      {(schema.fields || []).length === 0 ? (
        <div className="dim text-xs">This broker needs no credentials — it's the in-app paper broker.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {schema.fields.map((f) => (
            <div key={f.name}>
              <label className="block dim text-[10px] mono uppercase tracking-widest mb-1">
                {f.label} {f.required && <span className="sell">*</span>}
              </label>
              <input
                className="terminal"
                type={f.type === "number" ? "number" : "text"}
                style={f.type === "password" ? { WebkitTextSecurity: "disc" } : {}}
                value={values[f.name] || ""}
                onChange={(e) => onChange({ ...values, [f.name]: e.target.value })}
                placeholder={f.help || ""}
                autoComplete="off"
                data-testid={`broker-field-${f.name}`}
              />
              {f.help && <div className="dim text-[10px] mt-1">{f.help}</div>}
            </div>
          ))}
        </div>
      )}
      <div className="space-y-2 p-3 bg-[#FCFAF8] border border-[#E8E0D5] rounded-md">
        {accountType === "primary" ? (
          <div className="text-sm">
            <span className="font-semibold text-[var(--brand)]">Primary Account</span>
            <p className="dim text-xs mt-1">This account will strictly be used to pull live market data and populate charts. Order execution is completely disabled for safety.</p>
          </div>
        ) : (
          <div className="text-sm">
            <span className="font-semibold text-[var(--brand)]">Secondary Account</span>
            <p className="dim text-xs mt-1 mb-3">This account will strictly be used to execute your trades. Live data fetching is offloaded to the Primary account.</p>
            <label className="flex items-center gap-2 text-xs mono p-2 border-l-2 border-[var(--brand)] bg-white rounded">
              <input type="checkbox" checked={mockMode} onChange={(e) => onMockChange(e.target.checked)} />
              <span className="uppercase tracking-widest">Mock mode (Orders go to internal paper broker)</span>
            </label>
          </div>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-primary" onClick={onSave} data-testid="broker-save-btn">Save</button>
        {extras}
      </div>
    </div>
  );
}
