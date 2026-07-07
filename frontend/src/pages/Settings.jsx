/* eslint-disable */
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import Panel from "@/components/Panel";
import { PaperPlaneTilt, TestTube, Trash, DeviceMobile, Fingerprint } from "@phosphor-icons/react";
import { registerPush, unregisterPush, isNativeApp } from "@/lib/push";
import { clearBiometricCredentials, hasSavedCredentials, isBiometricAvailable } from "@/lib/biometric";

export default function Settings() {
  const { user, logout } = useAuth();
  const [tg, setTg] = useState({ bot_token: "", chat_id: "", enabled: true });
  const [status, setStatus] = useState({ configured: false, enabled: false, has_token: false, chat_id: "" });
  const [push, setPush] = useState({ enabled: false, device_count: 0, fcm_configured: false });
  const [native] = useState(isNativeApp());
  const [bio, setBio] = useState({ available: false, hasSaved: false, biometryType: "" });

  const load = async () => {
    const [a, b] = await Promise.all([
      api.get("/notifications/telegram"),
      api.get("/notifications/push"),
    ]);
    setStatus(a.data);
    setTg((t) => ({ ...t, chat_id: a.data.chat_id || t.chat_id, enabled: a.data.enabled }));
    setPush(b.data);
    const av = await isBiometricAvailable();
    const saved = av.available ? await hasSavedCredentials() : false;
    setBio({ available: av.available, hasSaved: saved, biometryType: av.biometryType || "" });
  };
  useEffect(() => { load(); }, []);

  const togglePush = async (enabled) => {
    if (enabled) {
      if (!native) {
        toast.error("Push only works inside the Android app build. Use Telegram in browser.");
        return;
      }
      const r = await registerPush();
      if (!r.ok) {
        toast.error(`Push setup failed: ${r.reason}`);
        return;
      }
      await api.post("/notifications/push/preferences", { enabled: true });
      toast.success("Push notifications enabled on this device");
    } else {
      await api.post("/notifications/push/preferences", { enabled: false });
      await unregisterPush();
      toast.success("Push notifications disabled");
    }
    load();
  };

  const testPush = async () => {
    try {
      await api.post("/notifications/push/test");
      toast.success("Test push sent — check your device");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Test failed");
    }
  };

  const save = async () => {
    await api.post("/notifications/telegram", tg);
    toast.success("Telegram settings saved");
    setTg({ ...tg, bot_token: "" });
    load();
  };
  const test = async () => {
    try {
      const { data } = await api.post("/notifications/telegram/test");
      if (data?.ok) toast.success("Test message sent to your chat ✅");
      else toast.error(data?.description || "Telegram rejected the test message");
    } catch (e) { toast.error(e?.response?.data?.detail || "Test failed"); }
  };
  const remove = async () => {
    await api.delete("/notifications/telegram");
    setTg({ bot_token: "", chat_id: "", enabled: true });
    load();
    toast.success("Telegram cleared");
  };

  return (
    <div className="space-y-4" data-testid="settings-page">
      <div>
        <h1 style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 28, letterSpacing: "-0.02em" }}>Settings.</h1>
        <p className="dim text-sm mt-1">Account, notifications & integrations.</p>
      </div>
      <Panel title="Account" kicker={user?.id}>
        <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-px bg-[#222]">
          <div className="bg-[#121212] p-4">
            <div className="dim text-[10px] mono uppercase tracking-widest">Name</div>
            <div className="mt-1 text-sm">{user?.name}</div>
          </div>
          <div className="bg-[#121212] p-4">
            <div className="dim text-[10px] mono uppercase tracking-widest">Email</div>
            <div className="mt-1 text-sm mono">{user?.email}</div>
          </div>
          <div className="bg-[#121212] p-4">
            <div className="dim text-[10px] mono uppercase tracking-widest">Role</div>
            <div className="mt-1 text-sm mono buy">{user?.role}</div>
          </div>
        </div>
        <div className="p-6 border-t border-[#222]">
          <button className="btn btn-danger" onClick={logout} data-testid="settings-logout-btn">Sign out</button>
        </div>
      </Panel>

      <Panel title="Telegram alerts" kicker={status.using_platform_bot ? "using platform bot" : status.configured ? "configured" : "not configured"}>
        <div className="p-4 space-y-3 text-xs">
          {status.platform_bot_available && (
            <div className="bg-[#1A1A1A] border border-[#00E676] p-3 text-xs buy">
              ✨ Platform bot available — you only need to paste your chat ID below. Skip the bot token field unless you want to use your own bot.
            </div>
          )}
          <div className="dim">
            How to set up your own bot (optional):
            <ol className="list-decimal pl-5 mt-1 space-y-0.5">
              <li>Open Telegram → talk to <span className="mono">@BotFather</span> → <span className="mono">/newbot</span> → copy the token.</li>
              <li>Start a chat with your bot, then visit <span className="mono">https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</span> to find your <span className="mono">chat.id</span>.</li>
              <li>Paste both below.</li>
            </ol>
            <div className="mt-2">For platform bot: just DM <span className="mono">@AlgonidAlertsBot</span> once, then paste your chat ID below.</div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <input className="terminal md:col-span-2" type="password" placeholder={status.has_token ? "•••••• (token saved — leave blank to keep)" : (status.platform_bot_available ? "Bot token (optional — leave blank to use platform bot)" : "Bot token from @BotFather")} value={tg.bot_token} onChange={(e) => setTg({ ...tg, bot_token: e.target.value })} data-testid="tg-bot-token" />
            <input className="terminal" placeholder="Chat ID (e.g. 123456789)" value={tg.chat_id} onChange={(e) => setTg({ ...tg, chat_id: e.target.value })} data-testid="tg-chat-id" />
          </div>
          <label className="flex items-center gap-2 text-xs mono">
            <input type="checkbox" checked={tg.enabled} onChange={(e) => setTg({ ...tg, enabled: e.target.checked })} data-testid="tg-enabled" />
            <span className="dim uppercase tracking-widest">Enabled — alerts forwarded to Telegram</span>
          </label>
          <div className="flex gap-2">
            <button className="btn btn-primary" onClick={save} data-testid="tg-save-btn">
              <PaperPlaneTilt size={14} weight="bold" /> Save
            </button>
            <button className="btn" onClick={test} data-testid="tg-test-btn" disabled={!status.configured && !(status.platform_bot_available && tg.chat_id)}>
              <TestTube size={14} weight="bold" /> Send test
            </button>
            {status.configured && (
              <button className="btn btn-danger" onClick={remove} data-testid="tg-clear-btn">
                <Trash size={14} weight="bold" /> Clear
              </button>
            )}
          </div>
        </div>
      </Panel>

      <Panel title="Push notifications" kicker={native ? (push.enabled ? "enabled" : "off") : "Android app only"}>
        <div className="p-4 space-y-3 text-xs">
          <div className="dim">
            Native push notifications (FCM) sent to the Algonid Android app — independent of Telegram.
            {!native && (
              <div className="mt-2 warn">
                <DeviceMobile size={14} weight="bold" className="inline mr-1" />
                You&apos;re on the browser. Install the Android app (see <span className="mono">/app/android/BUILD.md</span>) to receive push.
              </div>
            )}
            {!push.fcm_configured && (
              <div className="mt-2 sell">
                Server-side FCM key not configured yet — set <span className="mono">FCM_SERVER_KEY</span> in backend/.env to actually deliver pushes.
              </div>
            )}
          </div>
          <label className="flex items-center gap-2 text-xs mono">
            <input type="checkbox" checked={push.enabled} onChange={(e) => togglePush(e.target.checked)} data-testid="push-toggle" disabled={!native} />
            <span className="dim uppercase tracking-widest">Enable push notifications on this device</span>
          </label>
          <div className="dim mono text-[11px]">Devices registered: {push.device_count}</div>
          <div className="flex gap-2">
            <button className="btn" onClick={testPush} data-testid="push-test-btn" disabled={!push.enabled || push.device_count === 0}>
              <TestTube size={14} weight="bold" /> Send test push
            </button>
          </div>
        </div>
      </Panel>

      <Panel title="Biometric login" kicker={native ? (bio.available ? (bio.hasSaved ? "enabled" : "available") : "device has no biometrics") : "Android app only"}>
        <div className="p-4 space-y-3 text-xs">
          <div className="dim">
            <Fingerprint size={14} weight="bold" className="inline mr-1" />
            Use fingerprint or face unlock to sign into the Algonid Android app.
            Credentials are stored in the device&apos;s secure keychain — never sent to the server.
          </div>
          {!native && (
            <div className="warn">Only works inside the Android app build.</div>
          )}
          {native && bio.available && !bio.hasSaved && (
            <div className="dim">
              Sign out, then log in again with your password on the device — you&apos;ll be prompted to enable biometric login.
            </div>
          )}
          {native && bio.available && bio.hasSaved && (
            <div className="flex gap-2 items-center">
              <span className="buy mono">{bio.biometryType || "ENABLED"}</span>
              <button className="btn btn-danger" data-testid="biometric-clear-btn"
                onClick={async () => {
                  await clearBiometricCredentials();
                  toast.success("Biometric credentials removed");
                  load();
                }}>
                <Trash size={14} weight="bold" /> Forget device credentials
              </button>
            </div>
          )}
        </div>
      </Panel>
    </div>
  );
}
