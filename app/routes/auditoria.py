"""Endpoints para inspección y validación de la bitácora inmutable de auditoría — Módulo 9."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, desc, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models.auditoria import Auditoria
from app.models.usuario import Usuario
from app.services.auditoria import verificar_cadena

router = APIRouter(prefix="/api/auditoria", tags=["auditoria"])


class AuditoriaResponse(BaseModel):
    """Representación pública de un registro de auditoría."""

    id: int
    usuario_id: int
    usuario_nombre: str | None = None
    accion: str
    entidad: str
    entidad_id: int
    hash_anterior: str
    hash_actual: str
    timestamp: datetime


def _verificar_rol_medico(usuario: Usuario):
    """Garantiza que solo usuarios con rol MEDICO puedan auditar."""
    if usuario.rol != "MEDICO":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operación permitida únicamente para médicos",
        )


@router.get("", response_model=list[AuditoriaResponse])
def ruta_listar_auditoria(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> list[AuditoriaResponse]:
    """Lista los registros inmutables de auditoría (solo rol MEDICO)."""
    _verificar_rol_medico(usuario)

    registros = db.exec(
        select(Auditoria).order_by(desc(Auditoria.id))
    ).all()

    usuarios_cache = {}
    resultado = []
    for r in registros:
        if r.usuario_id not in usuarios_cache:
            u = db.get(Usuario, r.usuario_id)
            usuarios_cache[r.usuario_id] = u.nombre if u else f"ID {r.usuario_id}"

        resultado.append(
            AuditoriaResponse(
                id=r.id,
                usuario_id=r.usuario_id,
                usuario_nombre=usuarios_cache[r.usuario_id],
                accion=r.accion,
                entidad=r.entidad,
                entidad_id=r.entidad_id,
                hash_anterior=r.hash_anterior,
                hash_actual=r.hash_actual,
                timestamp=r.timestamp,
            )
        )

    return resultado


@router.get("/verificar")
def ruta_verificar_auditoria(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """Verifica la integridad criptográfica de toda la cadena de auditoría (solo rol MEDICO)."""
    _verificar_rol_medico(usuario)

    valida = verificar_cadena(db)
    return {
        "cadena_valida": valida,
        "mensaje": "La cadena de auditoría es íntegra y válida" if valida else "Se detectó alteración en la cadena de auditoría",
    }
