export async function isBiometricAvailable() {
  return { available: false, biometryType: "" };
}

export async function hasSavedCredentials() {
  return false;
}

export async function biometricSignIn() {
  return null;
}

export async function saveCredentials(email, password) {
  return false;
}

export async function clearBiometricCredentials() {
  return false;
}
