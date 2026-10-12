"""Servicio de reportes y KPIs para Alta.

100% Python puro. Sin IA. Sin red. Determinista.
Calcula métricas financieras, demográficas y clínicas
directamente desde la base de datos SQLite.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session, func, select

from app.models.cita import Cita
from app.models.consulta import Consulta
from app.models.paciente import Paciente
from app.models.pago import Pago
from app.models.usuario import Usuario


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _inicio_mes(año: int, mes: int) -> datetime:
    return datetime(año, mes, 1, 0, 0, 0, tzinfo=timezone.utc)


def _fin_mes(año: int, mes: int) -> datetime:
    """Último microsegundo del mes."""
    if mes == 12:
        return datetime(año + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc) - timedelta(microseconds=1)
    return datetime(año, mes + 1, 1, 0, 0, 0, tzinfo=timezone.utc) - timedelta(microseconds=1)


def _rango_periodo(periodo: str) -> tuple[datetime, datetime]:
    """Devuelve (inicio, fin) para los períodos: hoy, semana, mes, año."""
    ahora = datetime.now(timezone.utc)
    hoy = ahora.date()
    if periodo == "hoy":
        inicio = datetime(hoy.year, hoy.month, hoy.day, tzinfo=timezone.utc)
        fin = inicio + timedelta(days=1) - timedelta(microseconds=1)
    elif periodo == "semana":
        lunes = hoy - timedelta(days=hoy.weekday())
        inicio = datetime(lunes.year, lunes.month, lunes.day, tzinfo=timezone.utc)
        fin = inicio + timedelta(days=7) - timedelta(microseconds=1)
    elif periodo == "año":
        inicio = datetime(hoy.year, 1, 1, tzinfo=timezone.utc)
        fin = datetime(hoy.year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    else:  # mes (default)
        inicio = _inicio_mes(hoy.year, hoy.month)
        fin = _fin_mes(hoy.year, hoy.month)
    return (inicio, fin)


# ---------------------------------------------------------------------------
# KPIs Financieros
# ---------------------------------------------------------------------------

def kpi_financiero(db: Session, consultorio_id: int, periodo: str = "mes") -> dict:
    """Calcula KPIs financieros del período.

    Retorna:
        total_usd: float — ingresos totales en USD
        total_bs: float — ingresos en Bs (usando tasa_bcv_aplicada si existe, si no 0)
        num_pagos: int — número de pagos registrados
        promedio_usd: float — pago promedio en USD
        por_metodo: dict — monto por método de pago
        por_mes: list[dict] — ingresos de los últimos 12 meses
    """
    inicio, fin = _rango_periodo(periodo)

    pagos = db.exec(
        select(Pago).where(
            Pago.consultorio_id == consultorio_id,
            Pago.estado == "pagado",
            Pago.demo == False,
            Pago.fecha >= inicio,
            Pago.fecha <= fin,
        )
    ).all()

    total_usd = sum(p.monto for p in pagos if p.moneda == "USD")
    total_bs = sum(p.monto for p in pagos if p.moneda == "BS")
    # Convertir USD a Bs si hay tasa disponible
    total_bs_convertido = sum(
        p.monto * (p.tasa_bcv_aplicada or 0)
        for p in pagos
        if p.moneda == "USD" and p.tasa_bcv_aplicada
    )

    por_metodo: dict[str, float] = {}
    for p in pagos:
        metodo = p.metodo or "Sin especificar"
        por_metodo[metodo] = round(por_metodo.get(metodo, 0.0) + p.monto, 2)

    # Últimos 12 meses
    hoy = date.today()
    por_mes = []
    for i in range(11, -1, -1):
        m = (hoy.month - i - 1) % 12 + 1
        a = hoy.year - ((i - hoy.month + 1) // 12 + (1 if i >= hoy.month else 0))
        ini_m = _inicio_mes(a, m)
        fin_m = _fin_mes(a, m)
        pagos_mes = db.exec(
            select(Pago).where(
                Pago.consultorio_id == consultorio_id,
                Pago.estado == "pagado",
                Pago.demo == False,
                Pago.fecha >= ini_m,
                Pago.fecha <= fin_m,
                Pago.moneda == "USD",
            )
        ).all()
        por_mes.append({
            "mes": f"{a}-{m:02d}",
            "total": round(sum(p.monto for p in pagos_mes), 2),
            "num": len(pagos_mes),
        })

    return {
        "total_usd": round(total_usd, 2),
        "total_bs": round(total_bs, 2),
        "total_bs_estimado": round(total_bs_convertido, 2),
        "num_pagos": len(pagos),
        "promedio_usd": round(total_usd / len(pagos), 2) if pagos else 0.0,
        "por_metodo": por_metodo,
        "por_mes": por_mes,
    }


# ---------------------------------------------------------------------------
# KPIs Demográficos
# ---------------------------------------------------------------------------

def kpi_demografico(db: Session, consultorio_id: int) -> dict:
    """Calcula KPIs demográficos del consultorio.

    Retorna:
        total_pacientes: int
        humanos: int
        mascotas: int
        por_especie: dict — conteo de mascotas por especie
        rango_edades: dict — distribución de edades en rangos de 10 años
        con_alergias: int — pacientes con alergias registradas
        diabeticos: int — pacientes con es_diabetico=True
        hipertensos: int — pacientes con tiene_hipertension=True
    """
    pacientes = db.exec(
        select(Paciente).where(
            Paciente.consultorio_id == consultorio_id,
            Paciente.demo == False,
        )
    ).all()

    humanos = [p for p in pacientes if p.tipo == "HUMANO"]
    mascotas = [p for p in pacientes if p.tipo == "MASCOTA"]

    por_especie: dict[str, int] = {}
    for m in mascotas:
        esp = m.especie or "Sin especificar"
        por_especie[esp] = por_especie.get(esp, 0) + 1

    hoy = date.today()
    rango_edades: dict[str, int] = {
        "0-9": 0, "10-19": 0, "20-29": 0, "30-39": 0,
        "40-49": 0, "50-59": 0, "60-69": 0, "70+": 0,
    }
    for p in humanos:
        if p.fecha_nacimiento:
            edad = (hoy - p.fecha_nacimiento).days // 365
            if edad < 10:
                rango_edades["0-9"] += 1
            elif edad < 20:
                rango_edades["10-19"] += 1
            elif edad < 30:
                rango_edades["20-29"] += 1
            elif edad < 40:
                rango_edades["30-39"] += 1
            elif edad < 50:
                rango_edades["40-49"] += 1
            elif edad < 60:
                rango_edades["50-59"] += 1
            elif edad < 70:
                rango_edades["60-69"] += 1
            else:
                rango_edades["70+"] += 1

    # Campos clínicos (pueden no existir en registros viejos)
    diabeticos = sum(1 for p in humanos if getattr(p, "es_diabetico", False))
    hipertensos = sum(1 for p in humanos if getattr(p, "tiene_hipertension", False))
    embarazadas = sum(1 for p in humanos if getattr(p, "esta_embarazada", False))
    anticoagulantes = sum(1 for p in humanos if getattr(p, "toma_anticoagulantes", False))

    return {
        "total_pacientes": len(pacientes),
        "humanos": len(humanos),
        "mascotas": len(mascotas),
        "por_especie": por_especie,
        "rango_edades": rango_edades,
        "con_alergias": sum(1 for p in pacientes if p.alergias),
        "diabeticos": diabeticos,
        "hipertensos": hipertensos,
        "embarazadas": embarazadas,
        "anticoagulantes": anticoagulantes,
    }


# ---------------------------------------------------------------------------
# KPIs Clínicos
# ---------------------------------------------------------------------------

def kpi_clinico(db: Session, consultorio_id: int, periodo: str = "mes") -> dict:
    """Calcula KPIs clínicos del período.

    Retorna:
        total_consultas: int
        consultas_por_dia: list[dict] — últimos 30 días
        top_motivos: list[dict] — top 10 motivos más frecuentes
        top_diagnosticos: list[dict] — top 10 diagnósticos
        top_medicamentos: list[dict] — top 10 medicamentos prescritos
        citas_completadas: int
        citas_canceladas: int
        tasa_asistencia: float (%)
    """
    inicio, fin = _rango_periodo(periodo)

    consultas = db.exec(
        select(Consulta).where(
            Consulta.consultorio_id == consultorio_id,
            Consulta.demo == False,
            Consulta.fecha >= inicio,
            Consulta.fecha <= fin,
        )
    ).all()

    # Top motivos
    conteo_motivos: dict[str, int] = {}
    conteo_diag: dict[str, int] = {}
    conteo_meds: dict[str, int] = {}

    for c in consultas:
        if c.motivo:
            motivo = c.motivo.strip()[:50]  # truncar para agrupar mejor
            conteo_motivos[motivo] = conteo_motivos.get(motivo, 0) + 1
        diag = getattr(c, "diagnostico_codigo", None) or ""
        if diag:
            conteo_diag[diag] = conteo_diag.get(diag, 0) + 1
        meds_raw = getattr(c, "medicamentos", None) or ""
        if meds_raw:
            for med in meds_raw.split(","):
                med = med.strip()
                if med:
                    conteo_meds[med] = conteo_meds.get(med, 0) + 1

    def _top(d: dict, n: int = 10) -> list[dict]:
        return [
            {"nombre": k, "conteo": v}
            for k, v in sorted(d.items(), key=lambda x: x[1], reverse=True)[:n]
        ]

    # Consultas por día (últimos 30 días)
    hoy = date.today()
    consultas_por_dia = []
    for i in range(29, -1, -1):
        dia = hoy - timedelta(days=i)
        ini_d = datetime(dia.year, dia.month, dia.day, tzinfo=timezone.utc)
        fin_d = ini_d + timedelta(days=1) - timedelta(microseconds=1)
        cnt = sum(
            1 for c in consultas
            if c.fecha and ini_d <= c.fecha.replace(tzinfo=timezone.utc) <= fin_d
        )
        consultas_por_dia.append({"fecha": dia.isoformat(), "consultas": cnt})

    # Citas del período (excluye solicitudes de horario libre)
    citas = db.exec(
        select(Cita).where(
            Cita.consultorio_id == consultorio_id,
            Cita.demo == False,
            Cita.origen != "solicitud",
            Cita.fecha_hora >= inicio,
            Cita.fecha_hora <= fin,
        )
    ).all() if hasattr(Cita, "demo") else []

    completadas = sum(1 for c in citas if getattr(c, "estado", "") == "completada")
    canceladas = sum(1 for c in citas if getattr(c, "estado", "") == "cancelada")
    total_citas = len(citas)
    tasa = round(completadas / total_citas * 100, 1) if total_citas else 0.0

    return {
        "total_consultas": len(consultas),
        "consultas_por_dia": consultas_por_dia,
        "top_motivos": _top(conteo_motivos),
        "top_diagnosticos": _top(conteo_diag),
        "top_medicamentos": _top(conteo_meds),
        "citas_completadas": completadas,
        "citas_canceladas": canceladas,
        "tasa_asistencia": tasa,
    }


# ---------------------------------------------------------------------------
# Función principal: reporte completo
# ---------------------------------------------------------------------------

def generar_reporte(
    db: Session,
    consultorio_id: int,
    periodo: str = "mes",
) -> dict:
    """Genera el reporte completo combinando financiero, demográfico y clínico.

    Determinista: mismo estado de BD + mismo período → mismo resultado.
    """
    return {
        "periodo": periodo,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "financiero": kpi_financiero(db, consultorio_id, periodo),
        "demografico": kpi_demografico(db, consultorio_id),
        "clinico": kpi_clinico(db, consultorio_id, periodo),
    }
