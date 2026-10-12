"""Endpoint de salud del sistema para monitoreo — Módulo 11."""

from pathlib import Path

from fastapi import APIRouter
from sqlmodel import Session, text

from app.config import DATABASE_URL, ENCRYPTION_KEY_FILE
from app.database import engine

router = APIRouter(tags=["health"])

_VERSION = "1.0.0"


@router.get("/health")
def health() -> dict:
    """Verifica el estado del sistema.

    No requiere autenticación.
    Comprueba:
    - Conexión activa a la base de datos
    - Existencia de la clave de cifrado Fernet
    - Que la tabla principal (usuario) existe

    Retorna {"status": "ok", "db": "ok", "version": "1.0.0"}
    o {"status": "error", ...} si algo falla.
    """
    estado_db = "error"
    detalle_db: str | None = None

    # Verificar conexión y existencia de tabla principal
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1 FROM usuario LIMIT 1"))
        estado_db = "ok"
    except Exception as exc:
        detalle_db = str(exc)

    # Verificar existencia de la clave de cifrado (variable de entorno o archivo)
    from app.config import ENCRYPTION_KEY
    clave_existe = bool(ENCRYPTION_KEY) or Path(ENCRYPTION_KEY_FILE).exists()

    estado_global = "ok" if (estado_db == "ok" and clave_existe) else "error"

    respuesta: dict = {
        "status": estado_global,
        "version": _VERSION,
        "db": estado_db,
        "clave_cifrado": "ok" if clave_existe else "error",
    }

    if detalle_db:
        respuesta["db_detalle"] = detalle_db

    return respuesta
