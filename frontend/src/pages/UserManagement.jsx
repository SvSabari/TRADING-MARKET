import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import Panel from "@/components/Panel";
import { Plus, Trash, PencilSimple, CheckCircle, XCircle, Plugs, Eye, FloppyDisk, X, User } from "@phosphor-icons/react";

function formatCurrency(val, compact = false) {
  const num = Number(val) || 0;
  if (!compact) {
    return "₹" + num.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  // For compact display if number is huge:
  if (Math.abs(num) >= 10000000) {
    return "₹" + (num / 10000000).toFixed(2) + " Cr";
  }
  if (Math.abs(num) >= 100000) {
    return "₹" + (num / 100000).toFixed(2) + " L";
  }
  return "₹" + num.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

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

  const rawCash = Number(data.cash) || 0;
  const fullText = "₹" + rawCash.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const displayCash = rawCash >= 1000000 ? formatCurrency(rawCash, true) : "₹" + rawCash.toLocaleString('en-IN', { maximumFractionDigits: 0 });

  return (
    <div className="flex flex-col text-right">
      {data.name && <span className="text-xs font-bold text-white truncate max-w-[130px]" title={data.name}>{toTitleCase(data.name)}</span>}
      <div className="flex flex-col items-end mt-0.5">
        <span className="text-[12px] font-bold font-outfit text-[#22C55E] whitespace-nowrap cursor-help" title={`Exact Live Balance: ${fullText}`}>
          {displayCash}
        </span>
        <span className="text-[9px] mono uppercase whitespace-nowrap font-semibold text-[#CBD5E1]">Cash Available</span>
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
  capital_allocation_pct: 100,
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

  const [capitalMetrics, setCapitalMetrics] = useState({});
  const [allocationInputs, setAllocationInputs] = useState({});
  const [savingAllocationId, setSavingAllocationId] = useState(null);
  const [selectedUserForSheet, setSelectedUserForSheet] = useState(null);

  const loadData = async () => {
    try {
      const [uRes, sRes, cRes] = await Promise.allSettled([
        api.get("/managed-users"),
        api.get("/managed-users/schemas"),
        api.get("/managed-users/capital-metrics"),
      ]);

      if (uRes.status === "fulfilled") {
        setUsers(uRes.value.data.users || []);
      }
      if (sRes.status === "fulfilled" && sRes.value.data?.schemas) {
        setSchemas(sRes.value.data.schemas);
      }
      if (cRes.status === "fulfilled" && cRes.value.data?.metrics) {
        setCapitalMetrics(cRes.value.data.metrics);
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
        capital_allocation_pct: parseFloat(form.capital_allocation_pct) || 100,
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
      capital_allocation_pct: u.capital_allocation_pct !== undefined ? u.capital_allocation_pct : 100,
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

  const handleAllocationInputChange = (userId, value) => {
    setAllocationInputs((prev) => ({ ...prev, [userId]: value }));
  };

  const saveAllocationPct = async (userId) => {
    const rawVal = allocationInputs[userId];
    const val = parseFloat(rawVal);
    if (isNaN(val) || val < 0 || val > 100) {
      toast.error("Allocation percentage must be between 0 and 100%");
      return;
    }
    setSavingAllocationId(userId);
    try {
      await api.patch(`/managed-users/${userId}`, { capital_allocation_pct: val });
      toast.success(`Saved capital allocation to ${val}%`);
      setAllocationInputs((prev) => {
        const next = { ...prev };
        delete next[userId];
        return next;
      });
      loadData();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to save capital allocation");
    } finally {
      setSavingAllocationId(null);
    }
  };

  const togglePlaceOrder = async (u) => {
    const nextVal = !u.place_order;
    try {
      await api.patch(`/managed-users/${u.id}`, { place_order: nextVal });
      toast.success(`Order permission set to ${nextVal ? "YES" : "NO"} for ${u.name}`);
      loadData();
    } catch (e) {
      toast.error("Failed to update order permission");
    }
  };

  const toggleAccountStatus = async (u) => {
    const nextVal = u.account_status === "active" ? "deactivated" : "active";
    try {
      await api.patch(`/managed-users/${u.id}`, { account_status: nextVal });
      toast.success(`Account status set to ${nextVal.toUpperCase()} for ${u.name}`);
      loadData();
    } catch (e) {
      toast.error("Failed to update account status");
    }
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
  const labelCls = "block text-[#E2E8F0] text-[11px] mono uppercase tracking-wider mb-1 font-bold";

  return (
    <div className="space-y-6" data-testid="user-management-page">
      <div>
        <h1 style={{ fontFamily: "Outfit", fontWeight: 700, fontSize: 28, letterSpacing: "-0.01em", color: "#FFFFFF" }}>
          User Management
        </h1>
        <p className="text-[#CBD5E1] text-sm mt-1">
          Add and manage users linked to your trading account. Customize exact broker credentials per broker (Alice Blue, Zerodha, ICICI, Angel One, Upstox, Fyers).
        </p>
      </div>

      {/* Add / Edit Form */}
      <Panel title={editId ? "Edit User Account" : "Add New User Account"} kicker={editId ? "editing" : "create account"}>
        <form autoComplete="off" onSubmit={(e) => { e.preventDefault(); save(); }} className="p-4 space-y-6">
          {/* Section 1: User Profile Info */}
          <div>
            <div className="text-xs mono uppercase tracking-widest mb-3 font-bold text-[#60A5FA]">
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
                <label className={labelCls}>Capital Allocation (%) *</label>
                <input
                  className={inputCls}
                  name="user_capital_allocation"
                  autoComplete="off"
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  placeholder="e.g. 20"
                  value={form.capital_allocation_pct !== undefined ? form.capital_allocation_pct : 100}
                  onChange={(e) => setField("capital_allocation_pct", e.target.value)}
                />
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
              <div className="text-xs mono uppercase tracking-widest font-bold text-[#60A5FA] flex items-center gap-2">
                <Plugs size={14} weight="bold" /> 2. Configured Brokers ({form.brokers.length} Broker{form.brokers.length > 1 ? "s" : ""})
              </div>
              <button type="button" className="btn text-xs flex items-center gap-1 py-1 px-3" onClick={addBrokerRow}>
                <Plus size={12} weight="bold" /> Add Another Broker
              </button>
            </div>
            {editId && (
              <div className="text-[10px] mono mb-3 px-3 py-2 rounded" style={{ background: "rgba(42,157,143,0.15)", border: "1px solid rgba(42,157,143,0.4)", color: "#2DD4BF" }}>
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
                        <span className="mono text-xs font-bold uppercase tracking-wider text-white">
                          Broker #{idx + 1}
                        </span>
                        <select className="terminal py-1 px-3 text-xs font-bold text-white" value={bRow.broker} onChange={(e) => changeBrokerType(idx, e.target.value)}>
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
                          {field.help && <div className="text-[#CBD5E1] text-[11px] mt-1 font-sans">{field.help}</div>}
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

      {/* Users Table: Clean, fits screen without horizontal scroll, with Centered Modal */}
      <Panel title="All User Accounts" kicker={`${users.length} registered accounts`}>
        <div className="w-full">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="dim text-[10px] uppercase tracking-wider border-b border-[#222]">
                <th className="text-left whitespace-nowrap" style={{ padding: "8px 8px" }}>User</th>
                <th className="text-center whitespace-nowrap" style={{ padding: "8px 6px" }}>Enrolled</th>
                <th className="text-right whitespace-nowrap" style={{ padding: "8px 8px" }}>Available Cash</th>
                <th className="text-center whitespace-nowrap" style={{ padding: "8px 6px" }}>Allocation</th>
                <th className="text-right whitespace-nowrap" style={{ padding: "8px 8px" }}>Used (₹)</th>
                <th className="text-center whitespace-nowrap" style={{ padding: "8px 4px" }}>Order</th>
                <th className="text-center whitespace-nowrap" style={{ padding: "8px 4px" }}>Status</th>
                <th className="text-center whitespace-nowrap" style={{ padding: "8px 6px" }}>Session</th>
                <th className="text-center whitespace-nowrap" style={{ padding: "8px 8px" }}>Actions</th>
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
                const currentInputVal = allocationInputs[u.id] !== undefined 
                  ? allocationInputs[u.id] 
                  : (u.capital_allocation_pct !== undefined ? u.capital_allocation_pct : 100);
                const hasUnsavedChange = allocationInputs[u.id] !== undefined && parseFloat(allocationInputs[u.id]) !== u.capital_allocation_pct;
                const isSaving = savingAllocationId === u.id;
                const cap = capitalMetrics[u.id] || {};

                return (
                  <tr key={u.id} className="hover:bg-[rgba(255,255,255,0.02)] transition-colors">
                    {/* User & Phone */}
                    <td className="whitespace-nowrap" style={{ padding: "8px 8px" }}>
                      <div className="font-bold text-[13px] text-white leading-snug">{u.name}</div>
                      <div className="mono text-[11px] text-[#CBD5E1]">{u.phone}</div>
                    </td>

                    {/* Enrollment Date */}
                    <td className="text-center mono text-[12px] text-[#E2E8F0] font-semibold whitespace-nowrap" style={{ padding: "8px 6px" }}>
                      {u.enrollment_date || (u.created_at ? new Date(u.created_at).toISOString().split("T")[0] : "-")}
                    </td>

                    {/* Profile & Wallet */}
                    <td className="text-right whitespace-nowrap" style={{ padding: "8px 8px" }}>
                      <UserProfileDetails userId={u.id} />
                    </td>

                    {/* Capital Allocation (%) with compact, clean input & Save button */}
                    <td className="text-center whitespace-nowrap" style={{ padding: "8px 6px" }}>
                      <div className="inline-flex items-center gap-1 justify-center">
                        <div className="flex items-center">
                          <input
                            type="number"
                            min="0"
                            max="100"
                            step="1"
                            className="mono font-bold text-xs text-center border border-[var(--border)] rounded bg-[var(--surface)] text-[var(--text-primary)] [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none focus:outline-none focus:border-[var(--brand)]"
                            style={{ width: "46px", padding: "2px 4px", margin: 0 }}
                            value={currentInputVal}
                            onChange={(e) => handleAllocationInputChange(u.id, e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                saveAllocationPct(u.id);
                              }
                            }}
                          />
                          <span className="mono font-bold text-[11px] text-[#E2E8F0] ml-0.5">%</span>
                        </div>
                        {hasUnsavedChange && (
                          <button
                            type="button"
                            className="btn btn-primary py-0.5 px-1.5 text-[9px] flex items-center gap-0.5 mono font-bold shadow-sm"
                            style={{ minWidth: "auto" }}
                            onClick={() => saveAllocationPct(u.id)}
                            disabled={isSaving}
                            title="Click to save updated allocation percentage"
                          >
                            <FloppyDisk size={10} weight="bold" />
                            {isSaving ? "..." : "Save"}
                          </button>
                        )}
                      </div>
                    </td>

                    {/* Amount Used (₹) */}
                    <td className="text-right whitespace-nowrap" style={{ padding: "8px 8px" }}>
                      {(() => {
                        const usedVal = Number(cap.amount_used || 0);
                        const fullUsed = "₹" + usedVal.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                        const displayUsed = usedVal >= 1000000 ? formatCurrency(usedVal, true) : fullUsed;
                        return (
                          <div title={`Committed: ${fullUsed}`}>
                            <div className="mono font-bold text-xs" style={{ color: usedVal > 0 ? "var(--sell)" : "#FFFFFF" }}>
                              {displayUsed}
                            </div>
                            <div className="text-[10px] mono font-semibold text-[#CBD5E1]">Committed</div>
                          </div>
                        );
                      })()}
                    </td>

                    {/* Order Permission: Clickable toggle for trader */}
                    <td className="text-center whitespace-nowrap" style={{ padding: "8px 4px" }}>
                      <button
                        type="button"
                        onClick={() => togglePlaceOrder(u)}
                        title="Click to toggle order permission"
                        className={`text-[10px] mono font-bold px-1.5 py-0.5 rounded cursor-pointer border transition-all ${
                          u.place_order
                            ? "buy border-green-500/30 hover:bg-green-500/20"
                            : "sell border-red-500/30 hover:bg-red-500/20"
                        }`}
                        style={{ background: u.place_order ? "rgba(0,230,118,0.1)" : "rgba(239,68,68,0.1)" }}
                      >
                        {u.place_order ? "YES" : "NO"}
                      </button>
                    </td>

                    {/* Account Status: Clickable toggle for trader */}
                    <td className="text-center whitespace-nowrap" style={{ padding: "8px 4px" }}>
                      <button
                        type="button"
                        onClick={() => toggleAccountStatus(u)}
                        title="Click to toggle account status (Active / Deactivated)"
                        className="text-[10px] mono font-bold px-1.5 py-0.5 rounded cursor-pointer border transition-all"
                        style={{
                          background: u.account_status === "active" ? "rgba(0,230,118,0.12)" : "rgba(239,68,68,0.12)",
                          color: u.account_status === "active" ? "var(--buy)" : "var(--sell)",
                          borderColor: u.account_status === "active" ? "rgba(0,230,118,0.3)" : "rgba(239,68,68,0.3)",
                        }}
                      >
                        {u.account_status.toUpperCase()}
                      </button>
                    </td>

                    {/* Session Status: Compact display whether the user has generated/updated session today */}
                    <td className="text-center whitespace-nowrap" style={{ padding: "8px 6px" }}>
                      <div className="flex flex-col gap-1 items-center">
                        {bList.length === 0 && <span className="text-[10px] dim mono">—</span>}
                        {bList.map((b, i) => (
                          <div key={i} className="flex items-center gap-1 px-1 py-0.5 rounded border border-[var(--border)]" style={{ background: "var(--bg)" }}>
                            <span className="text-[9px] mono uppercase font-bold dim">{b.broker.replace("_", " ")}:</span>
                            {b.session_generated ? (
                              <span className="flex items-center gap-0.5 text-[9px] mono font-bold text-green-500">
                                <CheckCircle size={10} weight="fill" className="buy" /> Updated
                              </span>
                            ) : (
                              <span className="flex items-center gap-0.5 text-[9px] mono font-bold text-red-400">
                                <XCircle size={10} weight="fill" className="sell" /> Not Updated
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </td>

                    {/* Actions: View Sheet, Edit, Del - Fully visible with generous breathing room */}
                    <td className="text-center whitespace-nowrap" style={{ padding: "8px 8px" }}>
                      <div className="flex items-center justify-center gap-1.5">
                        <button
                          type="button"
                          className="btn text-[10px] py-1 px-2 flex items-center gap-1 mono font-bold rounded"
                          style={{ background: "rgba(33, 150, 243, 0.12)", color: "#1E88E5", borderColor: "rgba(33, 150, 243, 0.3)" }}
                          onClick={() => setSelectedUserForSheet(u)}
                          title="View complete details in sheet"
                        >
                          <Eye size={12} weight="bold" /> View
                        </button>
                        <button
                          type="button"
                          className="btn text-[10px] py-1 px-1.5 rounded text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                          onClick={() => startEdit(u)}
                          title="Edit Account"
                        >
                          <PencilSimple size={13} weight="bold" />
                        </button>
                        <button
                          type="button"
                          className="btn text-[10px] py-1 px-1.5 rounded hover:bg-red-500/10"
                          style={{ color: "var(--sell)", borderColor: "rgba(239,68,68,0.25)" }}
                          onClick={() => setDeleteConfirmId(u.id)}
                          title="Delete Account"
                        >
                          <Trash size={13} weight="bold" />
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

      {/* Centered User Detail Sheet Modal: Perfectly centered, full view without clipping or scrolling */}
      {selectedUserForSheet && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm transition-opacity" onClick={() => setSelectedUserForSheet(null)}>
          <div
            className="w-full max-w-2xl rounded-xl p-5 space-y-4 shadow-2xl transition-all"
            style={{ background: "var(--surface)", border: "1px solid var(--border)", boxShadow: "0 20px 40px rgba(0,0,0,0.5)" }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between pb-3 border-b border-[var(--border)]">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg" style={{ background: "rgba(33, 150, 243, 0.15)", color: "#64B5F6" }}>
                  <User size={20} weight="bold" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-[var(--text-primary)]">{selectedUserForSheet.name}</h2>
                  <div className="mono text-xs dim">{selectedUserForSheet.phone}</div>
                </div>
              </div>
              <button
                type="button"
                className="btn p-1.5 rounded-lg hover:bg-[rgba(255,255,255,0.08)]"
                onClick={() => setSelectedUserForSheet(null)}
              >
                <X size={18} weight="bold" />
              </button>
            </div>

            {/* Section 1: Capital Allocation & Balances (3 distinct cards, no duplicate percentage) */}
            <div>
              <div className="dim text-[10px] mono uppercase tracking-widest font-bold text-[var(--brand)] mb-2">
                Capital Allocation & Usage ({selectedUserForSheet.capital_allocation_pct !== undefined ? selectedUserForSheet.capital_allocation_pct : 100}% Allowed)
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded-lg border border-[var(--border)]" style={{ background: "var(--bg)" }}>
                  <div className="text-[#BAC0D0] text-[10px] font-semibold mono uppercase tracking-wider">Total Allocated (₹)</div>
                  <div className="text-base font-bold mono mt-1 text-white">
                    ₹{Number(capitalMetrics[selectedUserForSheet.id]?.allocated_amount || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                  </div>
                  <div className="text-[10px] text-[#9BA1B2] mono mt-1">Permitted trading capital</div>
                </div>

                <div className="p-3 rounded-lg border border-[var(--border)]" style={{ background: "var(--bg)" }}>
                  <div className="text-[#BAC0D0] text-[10px] font-semibold mono uppercase tracking-wider">Amount Used (₹)</div>
                  <div className="text-base font-bold mono mt-1" style={{ color: (capitalMetrics[selectedUserForSheet.id]?.amount_used || 0) > 0 ? "var(--sell)" : "#FFFFFF" }}>
                    ₹{Number(capitalMetrics[selectedUserForSheet.id]?.amount_used || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                  </div>
                  <div className="text-[10px] text-[#9BA1B2] mono mt-1">Committed in positions/orders</div>
                </div>

                <div className="p-3 rounded-lg border border-[var(--border)]" style={{ background: "var(--bg)" }}>
                  <div className="text-[#BAC0D0] text-[10px] font-semibold mono uppercase tracking-wider">Available Remaining (₹)</div>
                  <div className="text-base font-bold mono mt-1 text-[#089981]">
                    ₹{Number(capitalMetrics[selectedUserForSheet.id]?.available_amount !== undefined ? capitalMetrics[selectedUserForSheet.id]?.available_amount : 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                  </div>
                  <div className="text-[10px] text-[#9BA1B2] mono mt-1">Free for new trades</div>
                </div>
              </div>
            </div>

            {/* Section 2: Account Details & Permissions */}
            <div>
              <div className="text-xs mono uppercase tracking-widest font-bold text-[#60A5FA] mb-2">
                Account Details & Permissions
              </div>
              <div className="grid grid-cols-3 gap-3 p-3.5 rounded-lg border border-[var(--border)] text-xs" style={{ background: "var(--bg)" }}>
                <div>
                  <span className="text-[#BAC0D0] text-[10px] mono font-semibold block mb-0.5">Enrollment Date:</span>
                  <span className="mono font-bold text-white text-[13px]">
                    {selectedUserForSheet.enrollment_date || (selectedUserForSheet.created_at ? new Date(selectedUserForSheet.created_at).toISOString().split("T")[0] : "-")}
                  </span>
                </div>
                <div>
                  <span className="text-[#BAC0D0] text-[10px] mono font-semibold block mb-0.5">Account Status:</span>
                  <span className="mono font-bold uppercase text-[12px]" style={{ color: selectedUserForSheet.account_status === "active" ? "var(--buy)" : "var(--sell)" }}>
                    {selectedUserForSheet.account_status}
                  </span>
                </div>
                <div>
                  <span className="text-[#BAC0D0] text-[10px] mono font-semibold block mb-0.5">Place Order:</span>
                  <span className="mono font-bold uppercase text-[12px]" style={{ color: selectedUserForSheet.place_order ? "var(--buy)" : "var(--sell)" }}>
                    {selectedUserForSheet.place_order ? "Yes" : "No"}
                  </span>
                </div>
                <div>
                  <span className="text-[#BAC0D0] text-[10px] mono font-semibold block mb-0.5">Profit %:</span>
                  <span className="mono font-bold text-white text-[13px]">{selectedUserForSheet.profit_pct}%</span>
                </div>
                <div className="col-span-2">
                  <span className="text-[#BAC0D0] text-[10px] mono font-semibold block mb-0.5">Bank Account:</span>
                  <span className="mono font-bold text-white text-[13px]">{selectedUserForSheet.bank_account || "Not provided"}</span>
                </div>
              </div>
            </div>

            {/* Section 3: Configured Brokers */}
            <div>
              <div className="text-xs mono uppercase tracking-widest font-bold text-[#60A5FA] mb-2">
                Configured Brokers ({(selectedUserForSheet.brokers || []).length})
              </div>
              <div className="space-y-2">
                {(selectedUserForSheet.brokers || []).map((b, idx) => (
                  <div key={idx} className="p-3 rounded-lg border border-[var(--border)] flex items-center justify-between" style={{ background: "var(--bg)" }}>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm mono uppercase text-white">{b.broker}</span>
                        <div className="flex items-center gap-1">
                          {b.session_generated ? <CheckCircle size={14} weight="fill" className="buy" /> : <XCircle size={14} weight="fill" className="sell" />}
                          <span className="text-[11px] mono font-bold text-[#BAC0D0]">
                            {b.session_generated ? "Token Active" : "Token Pending"}
                          </span>
                        </div>
                      </div>
                      <div className="text-xs mono mt-1 text-[#BAC0D0]">
                        Client Code: <strong className="text-white text-[13px]">{b.account_number || b.credentials?.user_id || "N/A"}</strong>
                      </div>
                    </div>
                    <div className="text-[11px] mono font-bold px-2.5 py-1 rounded border" style={{
                      background: b.session_generated ? "rgba(0,230,118,0.12)" : "rgba(239,68,68,0.12)",
                      color: b.session_generated ? "var(--buy)" : "var(--sell)",
                      borderColor: b.session_generated ? "rgba(0,230,118,0.3)" : "rgba(239,68,68,0.3)"
                    }}>
                      {b.session_generated ? "Session Active" : "Session Expired"}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Modal Footer Actions */}
            <div className="pt-3 border-t border-[var(--border)] flex items-center justify-end gap-2">
              <button
                type="button"
                className="btn py-1.5 px-3 text-xs"
                onClick={() => setSelectedUserForSheet(null)}
              >
                Close
              </button>
              <button
                type="button"
                className="btn btn-primary py-1.5 px-3.5 text-xs font-bold"
                onClick={() => {
                  const target = selectedUserForSheet;
                  setSelectedUserForSheet(null);
                  startEdit(target);
                }}
              >
                <PencilSimple size={12} weight="bold" className="mr-1 inline" /> Edit Account
              </button>
            </div>
          </div>
        </div>
      )}

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
