"""Servicio de cifrado simétrico Fernet para campos clínicos sensibles — Módulo 9."""

import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

CLAVE_PATH = Path("data/clave.key")
_fernet_instance: Optional[Fernet] = None


def _obtener_clave() -> bytes:
    """Obtiene o genera la clave simétrica Fernet de 32 bytes base64."""
    clave_env = os.getenv("ENCRYPTION_KEY")
    if clave_env:
        return clave_env.encode("utf-8")
    if not CLAVE_PATH.exists():
        CLAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
        clave = Fernet.generate_key()
        CLAVE_PATH.write_bytes(clave)
        try:
            os.chmod(CLAVE_PATH, 0o600)
        except OSError:
            pass  # En Windows algunos entornos no soportan chmod unix
    return CLAVE_PATH.read_bytes()


def get_fernet() -> Fernet:
    """Devuelve la instancia singleton de Fernet."""
    global _fernet_instance
    if _fernet_instance is None:
        clave = _obtener_clave()
        _fernet_instance = Fernet(clave)
    return _fernet_instance


def cifrar(texto: Optional[str]) -> str:
    """Cifra un texto plano utilizando Fernet. Retorna string base64 seguro."""
    if not texto:
        return ""
    # Heurística: si ya está cifrado con Fernet, no cifrar dos veces
    if texto.startswith("gAAAAA"):
        return texto
    f = get_fernet()
    token = f.encrypt(texto.encode("utf-8"))
    return token.decode("utf-8")


def descifrar(texto_cifrado: Optional[str]) -> str:
    """Descifra un texto cifrado con Fernet. Si está en texto plano, lo devuelve intacto."""
    if not texto_cifrado:
        return ""
    # Si no parece un token Fernet, retornar tal cual
    if not texto_cifrado.startswith("gAAAAA"):
        return texto_cifrado
    f = get_fernet()
    try:
        texto_plano = f.decrypt(texto_cifrado.encode("utf-8"))
        return texto_plano.decode("utf-8")
    except (InvalidToken, Exception):
        # En caso de error o clave diferente, retornar el texto tal cual
        return texto_cifrado
