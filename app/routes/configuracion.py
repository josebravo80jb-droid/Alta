"""Endpoints de la API de configuración del consultorio.

Proporciona acciones de administración como backup de la base de datos.
Solo accesible por usuarios con rol MEDICO.
"""

import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.database import get_session
from app.dependencies import get_current_user
from app.models.usuario import Usuario
from sqlmodel import Session

router = APIRouter(prefix="/api/configuracion", tags=["configuracion"])

# Ruta de la BD (relativa al directorio de trabajo, igual que en database.py)
_DB_PATH = Path("data/alta.db")
_BACKUP_DIR = Path("data/backups")


@router.get("/backup", include_in_schema=True)
def descargar_backup(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Genera una copia de seguridad de la base de datos y la devuelve como descarga.

    Solo accesible por rol MEDICO.
    Copia alta.db a data/backups/alta-YYYY-MM-DD.db y sirve el archivo.
    """
    if usuario.rol != "MEDICO":
        raise HTTPException(status_code=403, detail="Solo el médico puede descargar el backup")

    if not _DB_PATH.exists():
        raise HTTPException(status_code=404, detail="Base de datos no encontrada")

    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    fecha_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    nombre_backup = f"alta-{fecha_str}.db"
    ruta_backup = _BACKUP_DIR / nombre_backup

    shutil.copy2(_DB_PATH, ruta_backup)

    return FileResponse(
        path=str(ruta_backup),
        filename=nombre_backup,
        media_type="application/octet-stream",
    )


@router.get("/tasa-bcv")
def get_tasa_bcv(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Devuelve la tasa oficial BCV del día y la tasa de respaldo configurada."""
    from app.services.tasa_bcv import obtener_tasa_bcv, obtener_tasa_respaldo
    tasa = obtener_tasa_bcv(db=db, consultorio_id=usuario.consultorio_id)
    respaldo = obtener_tasa_respaldo(db=db, consultorio_id=usuario.consultorio_id)
    return {
        "tasa_bcv": tasa,
        "tasa_respaldo": respaldo,
        "moneda": "USD/VES",
    }


@router.post("/tasa-bcv/refrescar")
def refrescar_tasa_bcv(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Fuerza la actualización de la tasa BCV consultando a pyDolarVenezuela."""
    from app.services.tasa_bcv import obtener_tasa_bcv
    nueva_tasa = obtener_tasa_bcv(force_refresh=True, db=db, consultorio_id=usuario.consultorio_id)
    return {
        "mensaje": "Tasa BCV actualizada correctamente",
        "tasa_bcv": nueva_tasa,
    }


@router.post("/tasa-respaldo")
def actualizar_tasa_respaldo(
    datos: dict,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Actualiza la tasa de respaldo para el consultorio. Solo accesible por MÉDICO."""
    if usuario.rol != "MEDICO":
        raise HTTPException(status_code=403, detail="Solo el médico puede modificar la tasa de respaldo")

    nueva_tasa = float(datos.get("tasa_respaldo", 40.0))
    if nueva_tasa <= 0:
        raise HTTPException(status_code=400, detail="La tasa debe ser mayor a cero")

    from app.models.configuracion import Configuracion
    from sqlmodel import select
    cfg = db.exec(select(Configuracion).where(Configuracion.consultorio_id == usuario.consultorio_id)).first()
    if cfg:
        cfg.tasa_respaldo = nueva_tasa
        db.add(cfg)
        db.commit()
        db.refresh(cfg)

    return {"mensaje": "Tasa de respaldo actualizada", "tasa_respaldo": nueva_tasa}
