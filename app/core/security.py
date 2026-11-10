from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Optional, Union

import bcrypt
import jwt

from app.core.config import settings

BCRYPT_MAX_BYTES = 72  # bcrypt solo procesa los primeros 72 bytes de la contraseña


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña en texto plano coincide con el hash almacenado."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # Hash corrupto o contraseña que excede el límite de bcrypt
        return False


def get_password_hash(password: str) -> str:
    """Genera un hash seguro utilizando bcrypt con salt automático."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return get_password_hash("timing-attack-mitigation")


def fake_password_check() -> None:
    """Ejecuta una verificación bcrypt de costo equivalente cuando el usuario no existe.

    Así el tiempo de respuesta del login es similar exista o no el correo,
    evitando la enumeración de usuarios por diferencia de tiempos.
    """
    verify_password("invalid-password", _dummy_hash())


def create_access_token(
    subject: Union[str, Any],
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Genera un token JWT firmado con claims de expiración, sujeto (email) y rol RBAC."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode = {
        "exp": expire,
        "iat": now,
        "sub": str(subject),
        "rol": role,
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decodifica y valida (firma y expiración) un token JWT. Devuelve {} si es inválido."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        return {}
