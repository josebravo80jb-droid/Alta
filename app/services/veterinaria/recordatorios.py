"""Recordatorios de vacunas veterinarias próximas y vencidas."""

from datetime import date, timedelta
from typing import Any, List, Optional
from sqlmodel import Session, select

from app.models.consultorio import Consultorio
from app.models.dueno import Dueno
from app.models.paciente import Paciente
from app.models.vacuna import Vacuna
from app.services.whatsapp import generar_enlace_whatsapp


def generar_mensaje_recordatorio(mascota: Any, dueno: Any, vacuna: Any) -> str:
    """Genera el texto sugerido para el recordatorio por WhatsApp de la vacuna."""
    nombre_dueno = getattr(dueno, "nombre", "Dueño/a") if dueno else "Dueño/a"
    nombre_mascota = getattr(mascota, "nombre", "su mascota") if mascota else "su mascota"
    
    tipo_vacuna = getattr(vacuna, "tipo", None) or (
        vacuna.get("tipo") if isinstance(vacuna, dict) else (
            vacuna.get("vacuna") if isinstance(vacuna, dict) else "vacunación"
        )
    )
    
    fecha_prog = getattr(vacuna, "proxima_dosis", None) or (
        vacuna.get("proxima_dosis") if isinstance(vacuna, dict) else (
            vacuna.get("fecha_programada") if isinstance(vacuna, dict) else None
        )
    )
    fecha_str = fecha_prog.strftime("%d/%m/%Y") if hasattr(fecha_prog, "strftime") else str(fecha_prog or "próximamente")

    return (
        f"Hola {nombre_dueno}, le recordamos que la vacuna ({tipo_vacuna}) de su mascota "
        f"{nombre_mascota} tiene fecha programada para el {fecha_str}. "
        f"Por favor agenda una cita con nosotros. — AltaPet"
    )


def vacunas_proximas_7_dias(db: Session, consultorio_id: int) -> List[dict]:
    """Obtiene las vacunas registradas cuya próxima dosis es dentro de los próximos 7 días."""
    hoy = date.today()
    limite = hoy + timedelta(days=7)

    stmt = (
        select(Vacuna, Paciente)
        .join(Paciente, Vacuna.paciente_id == Paciente.id)
        .where(
            Vacuna.consultorio_id == consultorio_id,
            Vacuna.proxima_dosis >= hoy,
            Vacuna.proxima_dosis <= limite,
        )
        .order_by(Vacuna.proxima_dosis)
    )
    filas = db.exec(stmt).all()

    resultados = []
    for vac, pac in filas:
        dueno = db.get(Dueno, pac.dueno_id) if pac.dueno_id else None
        dias_restantes = (vac.proxima_dosis - hoy).days
        msg = generar_mensaje_recordatorio(pac, dueno, vac)
        
        wa_link = None
        if dueno and dueno.telefono:
            try:
                wa_link = generar_enlace_whatsapp(dueno.telefono, msg)
            except Exception:
                pass

        resultados.append({
            "vacuna_id": vac.id,
            "tipo_vacuna": vac.tipo,
            "fecha_programada": vac.proxima_dosis,
            "dias_restantes": dias_restantes,
            "mascota_id": pac.id,
            "mascota_nombre": pac.nombre,
            "dueno_nombre": dueno.nombre if dueno else "Sin dueño registrado",
            "dueno_telefono": dueno.telefono if dueno else None,
            "mensaje_recordatorio": msg,
            "whatsapp_link": wa_link,
        })

    return resultados


def vacunas_vencidas(db: Session, consultorio_id: int) -> List[dict]:
    """Obtiene las vacunas registradas cuya fecha de próxima dosis ya pasó."""
    hoy = date.today()

    stmt = (
        select(Vacuna, Paciente)
        .join(Paciente, Vacuna.paciente_id == Paciente.id)
        .where(
            Vacuna.consultorio_id == consultorio_id,
            Vacuna.proxima_dosis < hoy,
        )
        .order_by(Vacuna.proxima_dosis)
    )
    filas = db.exec(stmt).all()

    resultados = []
    for vac, pac in filas:
        dueno = db.get(Dueno, pac.dueno_id) if pac.dueno_id else None
        dias_vencida = (hoy - vac.proxima_dosis).days
        msg = generar_mensaje_recordatorio(pac, dueno, vac)

        wa_link = None
        if dueno and dueno.telefono:
            try:
                wa_link = generar_enlace_whatsapp(dueno.telefono, msg)
            except Exception:
                pass

        resultados.append({
            "vacuna_id": vac.id,
            "tipo_vacuna": vac.tipo,
            "fecha_programada": vac.proxima_dosis,
            "dias_vencida": dias_vencida,
            "mascota_id": pac.id,
            "mascota_nombre": pac.nombre,
            "dueno_nombre": dueno.nombre if dueno else "Sin dueño registrado",
            "dueno_telefono": dueno.telefono if dueno else None,
            "mensaje_recordatorio": msg,
            "whatsapp_link": wa_link,
        })

    return resultados
