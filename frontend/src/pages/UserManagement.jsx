import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import Panel from "@/components/Panel";
import { Plus, Trash, PencilSimple, CheckCircle, XCircle, Plugs } from "@phosphor-icons/react";

function UserProfileDetails({ userId }) {
  const [data, setData] = useState(null);
  
  useEffect(() => {
    Promise.all([
      api.get(`/brokers/profile?user_id=${userId}`).catch(() => ({ data: { error: true } })),
      api.get(`/brokers/funds?user_id=${userId}`).catch(() => ({ data: { error: true } }))
    ]).then(([profRes, fundRes]) => {
      const prof = profRes.data.profile || {};
      const funds = Array.isArray(fundRes.data.funds) ? fundRes.data.funds[0] : fundRes.data.funds || {};
      const error = profRes.data.error || fundRes.data.error;
      setData({
        error: !!error,
        name: prof.accountName || prof.clientName || prof.name || null,
        cash: funds.cashmarginavailable || funds.cash || funds.net || 0
      });
    }).catch(() => setData({ error: true }));
  }, [userId]);

  const toTitleCase = (str) => {
    if (!str) return str;
    return str.toString().toLowerCase().split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  };

  if (!data) return <span className="text-[10px] dim mono">Loading...</span>;
  if (data.error) return <span className="text-[10px] text-[var(--sell)] mono font-bold">No Broker</span>;

  return (
    <div className="flex flex-col text-right">
      {data.name && <span className="text-xs font-bold text-[var(--text-primary)] whitespace-nowrap">{toTitleCase(data.name)}</span>}
      <div className="flex flex-col items-end mt-0.5">
        <span className="text-[11px] font-bold font-outfit text-green-500 whitespace-nowrap">
          ₹{Number(data.cash).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
        </span>
        <span className="text-[8px] mono dim uppercase whitespace-nowrap">Cash Available</span>
      </div>
    </div>
  );
}

const BROKER_MAP = {
  "Alice Blue": "alice_blue",
  "ICICI Direct": "icici",
  "Zerodha": "zerodha",
  "Angel One": "angel",
  "Upstox": "upstox",
  "Fyers": "fyers",
};

const DEFAULT_SCHEMAS = {
  alice_blue: {
    name: "Alice Blue",
    fields: [
      { name: "user_id", label: "User ID / Client ID", type: "text", required: true, placeholder: "e.g. AB12345", help: "Your Alice Blue Client Code" },
      { name: "api_key", label: "API Key (App Code)", type: "text", required: true, placeholder: "App Code from Developer Portal" },
      { name: "api_secret", label: "API Secret", type: "password", required: true, placeholder: "App Secret Key" },
    ],
  },
  zerodha: {
    name: "Zerodha Kite Connect",
    fields: [
      { name: "api_key", label: "API Key", type: "text", required: true, placeholder: "From Kite Developer Console" },
      { name: "api_secret", label: "API Secret", type: "password", required: true, placeholder: "Shown on Kite App Creation" },
    ],
  },
  icici: {
    name: "ICICI Direct (Breeze)",
    fields: [
      { name: "api_key", label: "App Key / API Key", type: "text", required: true, placeholder: "Breeze App Key" },
      { name: "api_secret", label: "Secret Key", type: "password", required: true, placeholder: "Breeze Secret Key" },
      { name: "session_token", label: "Session Token", type: "password", required: true, placeholder: "Daily Session Token" },
    ],
  },
  angel: {
    name: "Angel One (SmartAPI)",
    fields: [
      { name: "api_key", label: "API Key", type: "text", required: true, placeholder: "Angel SmartAPI Key" },
      { name: "client_code", label: "Client Code", type: "text", required: true, placeholder: "Your Angel Client Code" },
      { name: "pin", label: "PIN / Password", type: "password", required: true, placeholder: "Account PIN" },
      { name: "totp_secret", label: "TOTP Secret Key", type: "password", required: true, placeholder: "Authenticator TOTP Secret" },
    ],
  },
  upstox: {
    name: "Upstox",
    fields: [
      { name: "api_key", label: "API Key", type: "text", required: true, placeholder: "Upstox API Key" },
      { name: "api_secret", label: "API Secret", type: "password", required: true, placeholder: "Upstox Secret Key" },
    ],
  },
  fyers: {
    name: "Fyers",
    fields: [
      { name: "api_key", label: "App ID / Client ID", type: "text", required: true, placeholder: "Fyers App ID" },
      { name: "api_secret", label: "Secret ID", type: "password", required: true, placeholder: "Fyers Secret ID" },
    ],
  },
};

const EMPTY_BROKER_ROW = {
  broker: "Alice Blue",
  credentials: {},
};

const EMPTY_FORM = {
  name: "",
  phone: "",
  password: "",
  bank_account: "",
  place_order: true,
  profit_pct: "",
  account_status: "active",
  brokers: [{ ...EMPTY_BROKER_ROW }],
};

function getBrokerSchema(brokerDisplayName, schemas) {
  const key = BROKER_MAP[brokerDisplayName] || brokerDisplayName.toLowerCase().replace(" ", "_");
  return schemas?.[key] || DEFAULT_SCHEMAS[key] || { fields: [] };
}

function isBankAccountValid(acc) {
  if (!acc) return true; // optional field
  const digits = acc.replace(/\s/g, "");
  return /^\d{9,18}$/.test(digits); // 9–18 digits for all Indian bank account formats
}

function isFormComplete(f, isEditing, schemas) {
  if (!f.name || !f.phone || (!isEditing && !f.password) || f.profit_pct === "") return false;
  if (f.bank_account && !isBankAccountValid(f.bank_account)) return false;
  if (!f.brokers || f.brokers.length === 0) return false;

  // When editing, skip broker credential checks since password-type fields are not
  // pre-loaded for security. The update will only change fields that are provided.
  if (isEditing) return true;

  for (const b of f.brokers) {
    const schema = getBrokerSchema(b.broker, schemas);
    for (const field of schema.fields || []) {
      if (field.required && !b.credentials?.[field.name]) {
        return false;
      }
    }
  }
  return true;
}

export default function UserManagement() {
  const [users, setUsers] = useState([]);
  const [schemas, setSchemas] = useState(DEFAULT_SCHEMAS);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editId, setEditId] = useState(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadData = async () => {
    try {
      const [uRes, sRes] = await Promise.allSettled([
        api.get("/managed-users"),
        api.get("/managed-users/schemas"),
      ]);

      if (uRes.status === "fulfilled") {
        setUsers(uRes.value.data.users || []);
      }
      if (sRes.status === "fulfilled" && sRes.value.data?.schemas) {
        setSchemas(sRes.value.data.schemas);
      }
    } catch (e) {
      toast.error("Failed to load user management data");
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const setField = (k, v) => setForm((prev) => ({ ...prev, [k]: v }));

  const changeBrokerType = (index, brokerDisplayName) => {
    setForm((prev) => {
      const updated = [...prev.brokers];
      updated[index] = { broker: brokerDisplayName, credentials: {} };
      return { ...prev, brokers: updated };
    });
  };

  const setCredentialField = (brokerIndex, fieldName, fieldValue) => {
    setForm((prev) => {
      const updated = [...prev.brokers];
      const creds = { ...(updated[brokerIndex].credentials || {}) };
      creds[fieldName] = fieldValue;
      updated[brokerIndex] = { ...updated[brokerIndex], credentials: creds };
      return { ...prev, brokers: updated };
    });
  };

  const addBrokerRow = () => {
    setForm((prev) => ({
      ...prev,
      brokers: [...prev.brokers, { ...EMPTY_BROKER_ROW }],
    }));
  };

  const removeBrokerRow = (index) => {
    if (form.brokers.length <= 1) {
      toast.error("At least one broker is required");
      return;
    }
    setForm((prev) => ({
      ...prev,
      brokers: prev.brokers.filter((_, i) => i !== index),
    }));
  };

  const save = async () => {
    if (!isFormComplete(form, !!editId, schemas)) {
      toast.error("Please fill all required profile and broker fields");
      return;
    }
    if (form.bank_account && !isBankAccountValid(form.bank_account)) {
      toast.error("Bank account number must be 9–18 digits (numbers only)");
      return;
    }
    setBusy(true);
    try {
      const formattedBrokers = form.brokers.map((b) => {
        const brokerKey = BROKER_MAP[b.broker] || b.broker.toLowerCase().replace(" ", "_");
        const creds = b.credentials || {};
        return {
          broker: brokerKey,
          api_key: creds.api_key || creds.user_id || creds.client_code || "",
          api_secret: creds.api_secret || creds.totp_secret || "",
          account_number: creds.user_id || creds.client_code || creds.account_number || "",
          account_password: creds.pin || creds.totp_secret || creds.account_password || "",
          credentials: creds,
        };
      });

      const payload = {
        name: form.name,
        phone: form.phone,
        password: form.password,
        bank_account: form.bank_account,
        place_order: form.place_order,
        profit_pct: parseFloat(form.profit_pct) || 0,
        account_status: form.account_status,
        brokers: formattedBrokers,
      };

      if (editId) {
        await api.patch(`/managed-users/${editId}`, payload);
        toast.success("User account updated successfully");
      } else {
        await api.post("/managed-users", payload);
        toast.success("User created with " + formattedBrokers.length + " broker configuration(s)");
      }
      setForm(EMPTY_FORM);
      setEditId(null);
      loadData();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to save user");
    } finally {
      setBusy(false);
    }
  };

  const executeDelete = async () => {
    if (!deleteConfirmId) return;
    try {
      await api.delete(`/managed-users/${deleteConfirmId}`);
      toast.success("User account deleted");
      loadData();
    } catch (e) {
      toast.error("Failed to delete user");
    } finally {
      setDeleteConfirmId(null);
    }
  };

  const startEdit = (u) => {
    const loadedBrokers = (u.brokers || []).map((b) => {
      const displayName =
        Object.entries(BROKER_MAP).find(([, v]) => v === b.broker)?.[0] || b.broker;
      
      const creds = b.credentials && Object.keys(b.credentials).length > 0
        ? { ...b.credentials }
        : {
            api_key: b.api_key || "",
            api_secret: b.api_secret || "",
            user_id: b.account_number || "",
            client_code: b.account_number || "",
            pin: b.account_password || "",
            account_number: b.account_number || "",
            account_password: b.account_password || "",
          };

      return {
        broker: displayName,
        credentials: creds,
      };
    });

    setForm({
      name: u.name,
      phone: u.phone,
      password: "",
      bank_account: u.bank_account || "",
      place_order: u.place_order,
      profit_pct: u.profit_pct,
      account_status: u.account_status,
      brokers: loadedBrokers.length > 0 ? loadedBrokers : [{ ...EMPTY_BROKER_ROW }],
    });
    setEditId(u.id);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };


  const cancelEdit = () => {
    setForm(EMPTY_FORM);
    setEditId(null);
  };

  const generateBrokerToken = async (userId, brokerKey) => {
    try {
      const { data } = await api.post(`/managed-users/${userId}/get-session/${brokerKey}`);
      if (data.login_url) {
        window.location.href = data.login_url;
        toast.success("Opening " + data.broker + " authentication page...");
      } else {
        toast.success(data.broker + " session token generated!");
      }
      loadData();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to generate session token");
    }
  };

  const inputCls = "terminal w-full";
  const labelCls = "block dim text-[10px] mono uppercase tracking-widest mb-1 font-semibold";

  return (
    <div className="space-y-6" data-testid="user-management-page">
      <div>
        <h1 style={{ fontFamily: "Outfit", fontWeight: 700, fontSize: 28, letterSpacing: "-0.01em" }}>
          User Management
        </h1>
        <p className="dim text-sm mt-1">
          Add and manage users linked to your trading account. Customize exact broker credentials per broker (Alice Blue, Zerodha, ICICI, Angel One, Upstox, Fyers).
        </p>
      </div>

      {/* Add / Edit Form */}
      <Panel title={editId ? "Edit User Account" : "Add New User Account"} kicker={editId ? "editing" : "create account"}>
        <form autoComplete="off" onSubmit={(e) => { e.preventDefault(); save(); }} className="p-4 space-y-6">
          {/* Section 1: User Profile Info */}
          <div>
            <div className="dim text-xs mono uppercase tracking-widest mb-3 font-bold text-[var(--brand)]">
              1. User Profile Details
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className={labelCls}>Full Name *</label>
                <input className={inputCls} name="user_fullname" autoComplete="off" placeholder="Full name" value={form.name} onChange={(e) => setField("name", e.target.value)} />
              </div>
              <div>
                <label className={labelCls}>Phone Number *</label>
                <input className={inputCls} name="user_phonenumber" autoComplete="off" placeholder="e.g. 9876543210" value={form.phone} onChange={(e) => setField("phone", e.target.value)} />
              </div>
              <div>
                <label className={labelCls}>Login Password {editId ? "(Optional)" : "*"}</label>
                <input className={inputCls} name="user_new_password" type="password" autoComplete="new-password" placeholder={editId ? "Leave blank to keep current" : "Set login password"} value={form.password} onChange={(e) => setField("password", e.target.value)} />
              </div>
              <div>
                <label className={labelCls}>Profit % *</label>
                <input className={inputCls} name="user_profitpct" autoComplete="off" type="number" step="0.01" placeholder="e.g. 5.0" value={form.profit_pct} onChange={(e) => setField("profit_pct", e.target.value)} />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-3">
              <div>
                <label className={labelCls}>Bank Account Number</label>
                <input
                  className={`${inputCls}${form.bank_account && !isBankAccountValid(form.bank_account) ? " border-red-500" : ""}`}
                  name="bank_account"
                  autoComplete="off"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  placeholder="9–18 digit account number"
                  value={form.bank_account || ""}
                  onChange={(e) => {
                    const val = e.target.value.replace(/[^0-9]/g, "");
                    setField("bank_account", val);
                  }}
                />
                {form.bank_account && !isBankAccountValid(form.bank_account) && (
                  <p className="text-[10px] mt-1" style={{ color: "var(--sell)" }}>Must be 9–18 digits (numbers only)</p>
                )}
              </div>
              <div>
                <label className={labelCls}>Place Order *</label>
                <select className="terminal w-full" value={form.place_order ? "yes" : "no"} onChange={(e) => setField("place_order", e.target.value === "yes")}>
                  <option value="yes">Yes (Allow trading on this account)</option>
                  <option value="no">No (Disable trading)</option>
                </select>
              </div>

              <div>
                <label className={labelCls}>Account Status *</label>
                <select className="terminal w-full" value={form.account_status} onChange={(e) => setField("account_status", e.target.value)}>
                  <option value="active">Active</option>
                  <option value="deactivated">Deactivated</option>
                </select>
              </div>
            </div>
          </div>

          <div className="border-t border-[#222]" />

          {/* Section 2: Dynamic Per-Broker Configurations */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="dim text-xs mono uppercase tracking-widest font-bold text-[var(--brand)] flex items-center gap-2">
                <Plugs size={14} weight="bold" /> 2. Configured Brokers ({form.brokers.length} Broker{form.brokers.length > 1 ? "s" : ""})
              </div>
              <button type="button" className="btn text-xs flex items-center gap-1 py-1 px-3" onClick={addBrokerRow}>
                <Plus size={12} weight="bold" /> Add Another Broker
              </button>
            </div>
            {editId && (
              <div className="text-[10px] mono dim mb-3 px-3 py-2 rounded" style={{ background: "rgba(42,157,143,0.08)", border: "1px solid rgba(42,157,143,0.2)", color: "var(--buy)" }}>
                ✎ <strong>Editing mode:</strong> Credential fields you leave blank will keep their existing values. Only fill in fields you want to change.
              </div>
            )}

            <div className="space-y-4">
              {form.brokers.map((bRow, idx) => {
                const schema = getBrokerSchema(bRow.broker, schemas);
                return (
                  <div key={idx} className="p-4 rounded border border-[var(--border)] relative space-y-4" style={{ background: "var(--bg)" }}>
                    <div className="flex items-center justify-between pb-2 border-b border-[var(--border)]">
                      <div className="flex items-center gap-3">
                        <span className="mono text-xs font-bold uppercase tracking-wider">
                          Broker #{idx + 1}
                        </span>
                        <select className="terminal py-1 px-3 text-xs font-bold" value={bRow.broker} onChange={(e) => changeBrokerType(idx, e.target.value)}>
                          {Object.keys(BROKER_MAP).map((bName) => (
                            <option key={bName} value={bName}>{bName}</option>
                          ))}
                        </select>
                      </div>

                      {form.brokers.length > 1 && (
                        <button type="button" className="btn text-[10px] py-1 px-2 flex items-center gap-1" style={{ color: "var(--sell)" }} onClick={() => removeBrokerRow(idx)}>
                          <Trash size={12} weight="bold" /> Remove Broker
                        </button>
                      )}
                    </div>

                    {/* Render exact dynamic credential fields required for this broker */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {schema.fields && schema.fields.map((field) => (
                        <div key={field.name}>
                          <label className={labelCls}>
                            {field.label} {field.required ? "*" : ""}
                          </label>
                          <input
                            className={inputCls}
                            type={field.type || "text"}
                            autoComplete="off"
                            placeholder={field.placeholder || ""}
                            value={bRow.credentials?.[field.name] || ""}
                            onChange={(e) => setCredentialField(idx, field.name, e.target.value)}
                          />
                          {field.help && <div className="dim text-[10px] mt-1">{field.help}</div>}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Form Actions */}
          <div className="flex items-center gap-3 pt-2">
            <button type="submit" className="btn btn-primary flex items-center gap-2" disabled={busy || !isFormComplete(form, !!editId, schemas)} data-testid="save-user-btn">
              <Plus size={14} weight="bold" />
              {busy ? "Saving…" : editId ? "Update User Account" : "Save User Account"}
            </button>
            {editId && (
              <button type="button" className="btn" onClick={cancelEdit}>Cancel</button>
            )}
            {!isFormComplete(form, !!editId, schemas) && (
              <span className="text-xs dim mono">Please fill all required profile and broker fields</span>
            )}
          </div>
        </form>
      </Panel>

      {/* Users Table */}
      <Panel title="All User Accounts" kicker={`${users.length} registered accounts`}>
        <div style={{ overflowX: "auto" }}>
          <table className="w-full text-xs">
            <thead>
              <tr className="dim text-[10px] uppercase tracking-widest border-b border-[#222]">
                <th className="text-left py-2 px-4 whitespace-nowrap">Name</th>
                <th className="text-left py-2 px-4 whitespace-nowrap">Phone</th>
                <th className="text-right p-4 font-semibold text-[var(--text-secondary)]">Profile & Wallet</th>
                <th className="text-left py-2 px-4">Configured Brokers</th>
                <th className="text-center py-2 px-4 whitespace-nowrap">Place Order</th>
                <th className="text-right py-2 px-4 whitespace-nowrap">Profit %</th>
                <th className="text-center py-2 px-4 whitespace-nowrap">Status</th>
                <th className="text-center py-2 px-4 whitespace-nowrap">Session Actions</th>
                <th className="text-center py-2 px-4 whitespace-nowrap">Actions</th>
              </tr>
            </thead>
            <tbody className="cell-divider">
              {users.length === 0 && (
                <tr>
                  <td colSpan={9} className="p-8 text-center dim text-xs">
                    No users added yet. Fill out the form above to add your first user.
                  </td>
                </tr>
              )}
              {users.map((u) => {
                const bList = u.brokers || [];
                return (
                  <tr key={u.id} className="hover:bg-[rgba(255,255,255,0.02)] transition-colors">
                    <td className="py-3 px-4 font-bold whitespace-nowrap">{u.name}</td>
                    <td className="py-3 px-4 mono whitespace-nowrap">{u.phone}</td>
                    <td className="p-4 text-right">
                      <UserProfileDetails userId={u.id} />
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex flex-wrap gap-1">
                        {bList.map((b, i) => (
                          <span key={i} className="px-2 py-0.5 rounded text-[10px] mono uppercase font-bold border border-[var(--border)]" style={{ background: "var(--bg)" }}>
                            {b.broker}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-center">
                      {u.place_order ? (
                        <span className="buy text-[10px] mono font-bold">YES</span>
                      ) : (
                        <span className="sell text-[10px] mono font-bold">NO</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right mono font-bold">{u.profit_pct}%</td>
                    <td className="py-3 px-4 text-center">
                      <span className="text-[10px] mono font-bold px-2 py-0.5 rounded" style={{
                        background: u.account_status === "active" ? "rgba(0,230,118,0.12)" : "rgba(239,68,68,0.12)",
                        color: u.account_status === "active" ? "var(--buy)" : "var(--sell)",
                      }}>
                        {u.account_status.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex flex-col gap-1 items-center">
                        {bList.map((b, i) => (
                          <div key={i} className="text-[9px] py-0.5 px-2 flex items-center gap-1 mono uppercase rounded border border-[var(--border)]" style={{ background: "var(--bg)" }}>
                            {b.session_generated ? <CheckCircle size={10} weight="fill" className="buy" /> : <XCircle size={10} weight="fill" className="sell" />}
                            {b.broker}: {b.session_generated ? "Token Active" : "Token Pending"}
                          </div>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-center gap-2">
                        <button className="btn text-[10px] flex items-center gap-1 py-1 px-2" onClick={() => startEdit(u)} title="Edit">
                          <PencilSimple size={10} weight="bold" /> Edit
                        </button>
                        <button className="btn text-[10px] flex items-center gap-1 py-1 px-2" style={{ color: "var(--sell)" }} onClick={() => setDeleteConfirmId(u.id)} title="Delete">
                          <Trash size={10} weight="bold" /> Del
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>

      {/* Delete Confirmation Modal */}
      {deleteConfirmId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="p-6 rounded-lg w-full max-w-sm" style={{ background: "var(--surface)", border: "1px solid var(--border)", boxShadow: "var(--shadow-lg)" }}>
            <h3 className="font-bold text-lg mb-2" style={{ color: "var(--text-primary)" }}>Delete User Account</h3>
            <p className="text-sm mb-6" style={{ color: "var(--text-secondary)" }}>
              Are you sure you want to permanently delete this user account? This action cannot be undone.
            </p>
            <div className="flex items-center justify-end gap-3">
              <button className="btn py-2 px-4" onClick={() => setDeleteConfirmId(null)}>Cancel</button>
              <button className="btn py-2 px-4" style={{ background: "var(--sell)", color: "white", border: "none" }} onClick={executeDelete}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
