"""
Cifra simétrica de campos sensíveis (certificado A1, senha do PFX, CSC token).

Usa Fernet (AES-128-CBC + HMAC-SHA256) com chave derivada de
settings.FIELD_ENCRYPTION_KEY via SHA-256. Separada de SECRET_KEY para que
rotacionar a chave do Django não invalide os certificados em repouso.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _get_fernet() -> Fernet:
    raw = getattr(settings, "FIELD_ENCRYPTION_KEY", None)
    if not raw:
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEY ausente. Defina no .env antes de usar core.crypto."
        )
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_bytes(plaintext: bytes) -> bytes:
    if plaintext is None:
        return None
    return _get_fernet().encrypt(plaintext)


def decrypt_bytes(ciphertext: bytes) -> bytes:
    if ciphertext is None:
        return None
    try:
        return _get_fernet().decrypt(bytes(ciphertext))
    except InvalidToken as exc:
        raise ValueError("Falha ao decifrar: chave inválida ou dado corrompido.") from exc


def encrypt_str(plaintext: str) -> bytes:
    if plaintext is None:
        return None
    return encrypt_bytes(plaintext.encode("utf-8"))


def decrypt_str(ciphertext: bytes) -> str:
    if ciphertext is None:
        return None
    return decrypt_bytes(ciphertext).decode("utf-8")
