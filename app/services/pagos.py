"""Servicio de lógica de negocio para pagos e ingresos — Módulo 8."""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlmodel import Session, col, desc, select

from app.models.pago import Pago
from app.models.paciente import Paciente
from app.models.usuario import Usuario
from app.schemas.pago import PagoCreate


def crear_pago(
    db: Session,
    data: PagoCreate,
    usuario: Usuario,
) -> Pago:
    """Crea y persiste un nuevo pago asociado al consultorio del usuario autenticado."""
    paciente = db.exec(
        select(Paciente).where(
            Paciente.id == data.paciente_id,
            Paciente.consultorio_id == usuario.consultorio_id,
        )
    ).first()
    if not paciente:
        raise ValueError("El paciente no existe o no pertenece a este consultorio.")

    from app.services.tasa_bcv import obtener_tasa_bcv
    tasa_actual = obtener_tasa_bcv(db=db, consultorio_id=usuario.consultorio_id)

    pago = Pago(
        consultorio_id=usuario.consultorio_id,
        paciente_id=data.paciente_id,
        consulta_id=data.consulta_id,
        monto=float(data.monto),
        moneda=data.moneda.upper() if data.moneda else "USD",
        metodo=data.metodo,
        estado=data.estado.lower() if data.estado else "pagado",
        fecha=datetime.now(timezone.utc),
        registrado_por=usuario.id,
        tasa_bcv_aplicada=tasa_actual,
    )
    db.add(pago)
    db.commit()
    db.refresh(pago)
    return pago


def listar_pagos(
    db: Session,
    consultorio_id: int,
    mes: Optional[str] = None,
) -> list[Pago]:
    """Lista pagos del consultorio, con filtrado opcional por mes en formato 'YYYY-MM'."""
    stmt = select(Pago).where(Pago.consultorio_id == consultorio_id)

    if mes and len(mes) == 7 and "-" in mes:
        try:
            anio, mes_num = map(int, mes.split("-"))
            # Filtrar por año y mes usando comparación de fechas
            inicio_mes = datetime(anio, mes_num, 1, 0, 0, 0, tzinfo=timezone.utc)
            if mes_num == 12:
                fin_mes = datetime(anio + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
            else:
                fin_mes = datetime(anio, mes_num + 1, 1, 0, 0, 0, tzinfo=timezone.utc)

            stmt = stmt.where(Pago.fecha >= inicio_mes, Pago.fecha < fin_mes)
        except ValueError:
            pass

    return list(db.exec(stmt.order_by(desc(Pago.fecha))).all())


def obtener_resumen_ingresos(
    db: Session,
    consultorio_id: int,
    mes: Optional[str] = None,
) -> dict[str, Any]:
    """Calcula totales de ingresos para un mes dado o el total histórico."""
    pagos = listar_pagos(db, consultorio_id, mes)

    total_cobrado = 0.0
    total_pendiente = 0.0
    cantidad_pagos = len(pagos)

    for p in pagos:
        if p.estado == "pagado":
            total_cobrado += p.monto
        elif p.estado == "pendiente":
            total_pendiente += p.monto

    promedio = (total_cobrado / cantidad_pagos) if cantidad_pagos > 0 else 0.0

    return {
        "total_cobrado": round(total_cobrado, 2),
        "total_pendiente": round(total_pendiente, 2),
        "cantidad_pagos": cantidad_pagos,
        "promedio": round(promedio, 2),
    }


def eliminar_pago(
    db: Session,
    pago_id: int,
    consultorio_id: int,
) -> bool:
    """Elimina un pago registrado perteneciente al consultorio."""
    pago = db.exec(
        select(Pago).where(
            Pago.id == pago_id,
            Pago.consultorio_id == consultorio_id,
        )
    ).first()

    if not pago:
        return False

    db.delete(pago)
    db.commit()
    return True
