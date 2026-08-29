"""Small, audited cryptographic boundary for Pentest-Mode project state."""

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

KDF_ITERATIONS = 480_000
KEY_LENGTH = 32
VERIFIER_CANARY = b"SPECTREHUD_VERIFY"


class DecryptionError(Exception):
    """Raised when encrypted project state cannot be authenticated/decrypted."""


def derive_key(password: str, salt: bytes, iterations: int = KDF_ITERATIONS) -> bytes:
    """Derive a Fernet-compatible key from a password with PBKDF2-HMAC-SHA256."""
    if not isinstance(password, str) or not password:
        raise ValueError("A non-empty password is required.")
    if not isinstance(salt, bytes) or len(salt) < 16:
        raise ValueError("KDF salt must be at least 16 bytes.")
    if not isinstance(iterations, int) or iterations < KDF_ITERATIONS:
        raise ValueError(f"KDF iterations must be at least {KDF_ITERATIONS}.")
    raw_key = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=KEY_LENGTH, salt=salt, iterations=iterations
    ).derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw_key)


def create_verifier(key: bytes) -> str:
    """Create a password verifier without retaining the password itself."""
    return Fernet(key).encrypt(VERIFIER_CANARY).decode("ascii")


def verify_password(key: bytes, verifier: str) -> bool:
    """Return whether *key* decrypts the stored verifier canary."""
    try:
        return Fernet(key).decrypt(verifier.encode("ascii")) == VERIFIER_CANARY
    except (InvalidToken, ValueError, TypeError, UnicodeEncodeError):
        return False


def encrypt_bytes(key: bytes, data: bytes) -> bytes:
    """Encrypt bytes with authenticated Fernet encryption."""
    return Fernet(key).encrypt(data)


def decrypt_bytes(key: bytes, data: bytes) -> bytes:
    """Decrypt bytes or expose a domain-specific failure to callers."""
    try:
        return Fernet(key).decrypt(data)
    except (InvalidToken, ValueError, TypeError) as exc:
        raise DecryptionError("Encrypted project state could not be decrypted.") from exc
