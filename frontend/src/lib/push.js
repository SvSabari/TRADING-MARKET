export function isNativeApp() {
  return false;
}

export async function registerPush() {
  return { ok: false, reason: "Push not supported in browser" };
}

export async function unregisterPush() {
  return false;
}
