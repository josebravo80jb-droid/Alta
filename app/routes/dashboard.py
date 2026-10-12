"""Endpoints de la API del dashboard."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models.cita import Cita
from app.models.paciente import Paciente
from app.models.pago import Pago
from app.models.usuario import Usuario
from app.schemas.dashboard import CitaResumen, ResumenDashboard

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _hoy_utc() -> date:
    """Devuelve la fecha actual en UTC."""
    return datetime.now(timezone.utc).date()


@router.get("/resumen", response_model=ResumenDashboard)
def resumen(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ResumenDashboard:
    """Calcula y devuelve el resumen del día para el consultorio del usuario."""
    cid = usuario.consultorio_id
    hoy = _hoy_utc()
    # Primer instante del mes actual (para filtrar ingresos del mes)
    primer_dia_mes = datetime(hoy.year, hoy.month, 1, tzinfo=timezone.utc)

    # ── Citas de hoy ─────────────────────────────────────────────────────────
    # Filtramos comparando la fecha (sin hora) usando SQLite strftime
    citas_hoy_rows = db.exec(
        select(Cita).where(
            Cita.consultorio_id == cid,
            func.date(Cita.fecha_hora) == str(hoy),
        )
    ).all()

    citas_hoy = len(citas_hoy_rows)
    citas_pendientes = sum(1 for c in citas_hoy_rows if c.estado == "pendiente")
    citas_completadas = sum(1 for c in citas_hoy_rows if c.estado == "completada")

    # ── Ingresos ──────────────────────────────────────────────────────────────
    pagos_hoy = db.exec(
        select(Pago).where(
            Pago.consultorio_id == cid,
            func.date(Pago.fecha) == str(hoy),
            Pago.estado == "pagado",
        )
    ).all()
    ingresos_hoy = sum(p.monto for p in pagos_hoy)

    pagos_mes = db.exec(
        select(Pago).where(
            Pago.consultorio_id == cid,
            Pago.fecha >= primer_dia_mes,
            Pago.estado == "pagado",
        )
    ).all()
    ingresos_mes = sum(p.monto for p in pagos_mes)

    # ── Total pacientes ───────────────────────────────────────────────────────
    total_pacientes = db.exec(
        select(func.count(Paciente.id)).where(Paciente.consultorio_id == cid)
    ).one()

    # ── Próximas 5 citas ──────────────────────────────────────────────────────
    ahora = datetime.now(timezone.utc)
    proximas_rows = db.exec(
        select(Cita, Paciente)
        .join(Paciente, Cita.paciente_id == Paciente.id)
        .where(
            Cita.consultorio_id == cid,
            Cita.fecha_hora >= ahora,
            Cita.estado.in_(["pendiente", "confirmada"]),
        )
        .order_by(Cita.fecha_hora)
        .limit(5)
    ).all()

    proximas_citas = [
        CitaResumen(
            id=cita.id,
            paciente_nombre=paciente.nombre,
            fecha_hora=cita.fecha_hora,
            motivo=cita.motivo,
            estado=cita.estado,
        )
        for cita, paciente in proximas_rows
    ]

    return ResumenDashboard(
        citas_hoy=citas_hoy,
        citas_pendientes=citas_pendientes,
        citas_completadas=citas_completadas,
        ingresos_hoy=round(ingresos_hoy, 2),
        ingresos_mes=round(ingresos_mes, 2),
        total_pacientes=total_pacientes,
        proximas_citas=proximas_citas,
    )
