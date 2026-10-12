"""Servicio de auditoría hash-chain inmutable — Módulo 9."""

import hashlib
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, desc, select

from app.models.auditoria import Auditoria


def _calcular_hash(
    usuario_id: int,
    accion: str,
    entidad: str,
    entidad_id: int,
    ts: datetime,
    hash_anterior: str,
) -> str:
    """Calcula SHA-256 de los campos constitutivos del registro de auditoría."""
    cadena = f"{usuario_id}:{accion}:{entidad}:{entidad_id}:{ts.isoformat()}:{hash_anterior}"
    return hashlib.sha256(cadena.encode("utf-8")).hexdigest()


def registrar(
    db: Session,
    usuario_id: int,
    accion: str,
    entidad: str,
    entidad_id: int,
) -> Auditoria:
    """Registra una acción en la bitácora encadenada mediante hash inmutable."""
    # Obtener el último registro para extraer su hash_actual como hash_anterior
    ultimo = db.exec(
        select(Auditoria).order_by(desc(Auditoria.id))
    ).first()

    hash_ant = ultimo.hash_actual if ultimo else "GENESIS"
    ahora = datetime.now(timezone.utc)
    hash_act = _calcular_hash(
        usuario_id=usuario_id,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        ts=ahora,
        hash_anterior=hash_ant,
    )

    registro = Auditoria(
        usuario_id=usuario_id,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        hash_anterior=hash_ant,
        hash_actual=hash_act,
        timestamp=ahora,
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return registro


def verificar_cadena(db: Session) -> bool:
    """Verifica la integridad de la cadena completa de auditoría.

    Comprueba que:
    1. Cada hash_actual coincide con el cómputo de sus datos.
    2. El hash_anterior de cada registro coincide con el hash_actual del registro previo.
    """
    registros = db.exec(
        select(Auditoria).order_by(Auditoria.id)
    ).all()

    if not registros:
        return True

    hash_esperado_anterior = "GENESIS"

    for r in registros:
        if r.hash_anterior != hash_esperado_anterior:
            return False

        hash_calculado = _calcular_hash(
            usuario_id=r.usuario_id,
            accion=r.accion,
            entidad=r.entidad,
            entidad_id=r.entidad_id,
            ts=r.timestamp,
            hash_anterior=r.hash_anterior,
        )

        if r.hash_actual != hash_calculado:
            return False

        hash_esperado_anterior = r.hash_actual

    return True
