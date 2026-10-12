"""Servicio de autenticación: hashing, verificación y JWT."""

from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.config import SECRET_KEY
from app.models.usuario import Usuario

# Algoritmo y duración del token
_ALGORITHM = "HS256"
_TOKEN_EXPIRE_HOURS = 24

# Instancia global del hasher (argon2 por defecto via extras)
_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Devuelve el hash argon2 del password en texto plano."""
    return _password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Retorna True si el password coincide con el hash almacenado."""
    return _password_hash.verify(password, hashed)


def crear_token(usuario: Usuario) -> str:
    """Genera un JWT firmado con HS256, válido por 24 horas."""
    expira = datetime.now(timezone.utc) + timedelta(hours=_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(usuario.id),
        "email": usuario.email,
        "rol": usuario.rol,
        "exp": expira,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=_ALGORITHM)


def decodificar_token(token: str) -> dict:
    """Decodifica y valida un JWT. Lanza jwt.PyJWTError si es inválido o expirado."""
    return jwt.decode(token, SECRET_KEY, algorithms=[_ALGORITHM])
