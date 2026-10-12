"""Endpoints para registro de pagos, recibos en PDF y reportes en CSV — Módulo 8."""

import csv
from io import StringIO
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models.consulta import Consulta
from app.models.consultorio import Consultorio
from app.models.paciente import Paciente
from app.models.pago import Pago
from app.models.usuario import Usuario
from app.schemas.pago import PagoCreate, PagoResponse
from app.services.pagos import (
    crear_pago,
    eliminar_pago,
    listar_pagos,
    obtener_resumen_ingresos,
)
from app.services.pdf import generar_recibo

router = APIRouter(tags=["pagos"])


@router.post("/api/pagos", response_model=PagoResponse, status_code=status.HTTP_201_CREATED)
def ruta_crear_pago(
    data: PagoCreate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> PagoResponse:
    """Registra un nuevo cobro/pago para un paciente."""
    try:
        pago = crear_pago(db=db, data=data, usuario=usuario)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))

    from app.services.auditoria import registrar as registrar_auditoria
    registrar_auditoria(db, usuario.id, "CREATE", "pago", pago.id)

    paciente = db.get(Paciente, pago.paciente_id)
    return PagoResponse(
        id=pago.id,
        paciente_id=pago.paciente_id,
        paciente_nombre=paciente.nombre if paciente else None,
        consulta_id=pago.consulta_id,
        monto=pago.monto,
        moneda=pago.moneda,
        metodo=pago.metodo,
        estado=pago.estado,
        fecha=pago.fecha,
        registrado_por_nombre=usuario.nombre,
    )


@router.get("/api/pagos", response_model=list[PagoResponse])
def ruta_listar_pagos(
    mes: Optional[str] = Query(None, description="Mes en formato YYYY-MM"),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> list[PagoResponse]:
    """Lista pagos del consultorio filtrados opcionalmente por mes."""
    pagos = listar_pagos(db=db, consultorio_id=usuario.consultorio_id, mes=mes)

    # Caches para optimizar nombres
    pacientes_cache = {}
    usuarios_cache = {}
    resultado = []

    for p in pagos:
        if p.paciente_id not in pacientes_cache:
            pac = db.get(Paciente, p.paciente_id)
            pacientes_cache[p.paciente_id] = pac.nombre if pac else None
        if p.registrado_por not in usuarios_cache:
            usr = db.get(Usuario, p.registrado_por)
            usuarios_cache[p.registrado_por] = usr.nombre if usr else None

        resultado.append(
            PagoResponse(
                id=p.id,
                paciente_id=p.paciente_id,
                paciente_nombre=pacientes_cache[p.paciente_id],
                consulta_id=p.consulta_id,
                monto=p.monto,
                moneda=p.moneda,
                metodo=p.metodo,
                estado=p.estado,
                fecha=p.fecha,
                registrado_por_nombre=usuarios_cache[p.registrado_por],
            )
        )

    return resultado


@router.get("/api/pagos/{id}/recibo")
def ruta_descargar_recibo(
    id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Genera y descarga el recibo en formato PDF para un pago registrado."""
    pago = db.exec(
        select(Pago).where(Pago.id == id, Pago.consultorio_id == usuario.consultorio_id)
    ).first()
    if not pago:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pago no encontrado")

    consultorio = db.get(Consultorio, pago.consultorio_id)
    paciente = db.get(Paciente, pago.paciente_id)
    consulta = db.get(Consulta, pago.consulta_id) if pago.consulta_id else None

    ruta_pdf = f"data/recibos/recibo_{pago.id}.pdf"
    if not os.path.exists(ruta_pdf):
        generar_recibo(pago=pago, consultorio=consultorio, paciente=paciente, consulta=consulta)

    return FileResponse(ruta_pdf, media_type="application/pdf", filename=f"recibo_{pago.id}.pdf")


@router.delete("/api/pagos/{id}")
def ruta_eliminar_pago(
    id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict[str, str]:
    """Elimina un pago registrado."""
    ok = eliminar_pago(db=db, pago_id=id, consultorio_id=usuario.consultorio_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pago no encontrado")

    from app.services.auditoria import registrar as registrar_auditoria
    registrar_auditoria(db, usuario.id, "DELETE", "pago", id)

    return {"mensaje": "Pago eliminado correctamente"}


@router.get("/api/ingresos")
def ruta_resumen_ingresos(
    mes: Optional[str] = Query(None, description="Mes en formato YYYY-MM"),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """Devuelve las métricas de ingresos para un mes dado o global."""
    return obtener_resumen_ingresos(db=db, consultorio_id=usuario.consultorio_id, mes=mes)


@router.get("/api/ingresos/export.csv")
def ruta_exportar_csv(
    mes: Optional[str] = Query(None, description="Mes en formato YYYY-MM"),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Exporta el historial de pagos filtrado por mes en formato CSV descargable."""
    pagos = listar_pagos(db=db, consultorio_id=usuario.consultorio_id, mes=mes)

    output = StringIO()
    writer = csv.writer(output)

    # Cabeceras requeridas
    writer.writerow(["Fecha", "Paciente", "Concepto", "Monto", "Moneda", "Método", "Estado"])

    for p in pagos:
        paciente = db.get(Paciente, p.paciente_id)
        consulta = db.get(Consulta, p.consulta_id) if p.consulta_id else None
        concepto = f"Consulta: {consulta.motivo}" if consulta else "Atención médica"

        writer.writerow([
            p.fecha.strftime("%d/%m/%Y %H:%M"),
            paciente.nombre if paciente else "—",
            concepto,
            f"{p.monto:.2f}",
            p.moneda,
            p.metodo.capitalize() if p.metodo else "Efectivo",
            p.estado.capitalize(),
        ])

    output.seek(0)
    filename = f"ingresos_{mes}.csv" if mes else "ingresos_total.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
