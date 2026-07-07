/* eslint-disable */
export default function BrokerForm({ schema, values, onChange, mockMode, onMockChange, onSave, extras }) {
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
      <label className="flex items-center gap-2 text-xs mono">
        <input type="checkbox" checked={mockMode} onChange={(e) => onMockChange(e.target.checked)} data-testid="broker-mock-toggle" />
        <span className="dim uppercase tracking-widest">Mock mode — orders go to the paper broker (recommended until you've tested keys)</span>
      </label>
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-primary" onClick={onSave} data-testid="broker-save-btn">Save</button>
        {extras}
      </div>
    </div>
  );
}
