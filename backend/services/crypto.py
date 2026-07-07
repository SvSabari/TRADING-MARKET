"""Symmetric encryption helpers (Fernet) for storing broker API secrets."""
import os
from cryptography.fernet import Fernet, InvalidToken

_KEY = (os.environ.get("KITE_FERNET_KEY") or os.environ.get("ENCRYPTION_KEY") or "").encode("utf-8")
try:
    _fernet = Fernet(_KEY) if _KEY else None
except Exception:
    _fernet = None


def encrypt_str(plaintext: str) -> str:
    if not _fernet or not plaintext:
        return plaintext
    return _fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_str(ciphertext: str) -> str:
    if not _fernet or not ciphertext:
        return ciphertext
    try:
        return _fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # legacy plain values may already be stored as-is
        return ciphertext
