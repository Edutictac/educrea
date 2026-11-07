from functools import lru_cache
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...config import get_settings
from ...models import AiCredential


@lru_cache
def cipher() -> MultiFernet:
    configured = get_settings().credential_keys
    if configured is None:
        raise HTTPException(503, "Cifrado de credenciales no configurado")
    try:
        keys = [Fernet(line.strip().encode()) for line in configured.get_secret_value().splitlines() if line.strip()]
        if not keys:
            raise ValueError("No keys")
        return MultiFernet(keys)
    except (ValueError, TypeError) as exc:
        raise HTTPException(503, "Cifrado de credenciales no configurado") from exc


def encrypt_key(value: str) -> str:
    return cipher().encrypt(value.encode()).decode()


def decrypt_key(value: str) -> str:
    try:
        return cipher().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise HTTPException(503, "No se puede descifrar la credencial") from exc


def rotate_ciphertext(value: str) -> str:
    try:
        return cipher().rotate(value.encode()).decode()
    except InvalidToken as exc:
        raise HTTPException(503, "No se puede descifrar la credencial") from exc


def personal_credential(db: Session, user_id: UUID, provider: str = "gemini") -> AiCredential | None:
    return db.scalar(select(AiCredential).where(AiCredential.user_id == user_id, AiCredential.provider == provider))

