"""Cálculo y seguimiento de calendarios de vacunación veterinaria."""

from datetime import date, timedelta
from typing import Any, List, Optional

CALENDARIO_VACUNAS = {
    "perro": [
        {"vacuna": "moquillo", "edad_semanas": 6, "refuerzo_semanas": 52},
        {"vacuna": "parvovirus", "edad_semanas": 6, "refuerzo_semanas": 52},
        {"vacuna": "hepatitis", "edad_semanas": 8, "refuerzo_semanas": 52},
        {"vacuna": "rabia", "edad_semanas": 12, "refuerzo_semanas": 52},
    ],
    "gato": [
        {"vacuna": "triple felina", "edad_semanas": 6, "refuerzo_semanas": 52},
        {"vacuna": "leucemia felina", "edad_semanas": 8, "refuerzo_semanas": 52},
        {"vacuna": "rabia", "edad_semanas": 12, "refuerzo_semanas": 52},
    ],
    "conejo": [
        {"vacuna": "mixomatosis", "edad_semanas": 4, "refuerzo_semanas": 26},
        {"vacuna": "vhd", "edad_semanas": 4, "refuerzo_semanas": 26},
    ],
    "equino": [
        {"vacuna": "rabia", "edad_semanas": 26, "refuerzo_semanas": 52},
        {"vacuna": "influenza equina", "edad_semanas": 26, "refuerzo_semanas": 26},
        {"vacuna": "tétanos", "edad_semanas": 26, "refuerzo_semanas": 52},
    ],
}


def calcular_calendario(especie: str, fecha_nacimiento: date) -> List[dict]:
    """Calcula el calendario de vacunas programadas iniciales y sus primeros refuerzos.

    Devuelve una lista ordenada cronológicamente de vacunas con fecha programada.
    """
    if not especie or not fecha_nacimiento:
        return []

    clave = str(especie).strip().lower()
    reglas = CALENDARIO_VACUNAS.get(clave, [])
    calendario = []

    for item in reglas:
        nombre_vac = item["vacuna"]
        # 1. Primera dosis
        dias_primera = item["edad_semanas"] * 7
        fecha_primera = fecha_nacimiento + timedelta(days=dias_primera)
        calendario.append({
            "vacuna": nombre_vac,
            "fecha_programada": fecha_primera,
            "dosis_numero": 1,
            "es_refuerzo": False,
        })

        # 2. Refuerzo anual / periódico
        if item.get("refuerzo_semanas"):
            dias_refuerzo = item["refuerzo_semanas"] * 7
            fecha_refuerzo = fecha_primera + timedelta(days=dias_refuerzo)
            calendario.append({
                "vacuna": nombre_vac,
                "fecha_programada": fecha_refuerzo,
                "dosis_numero": 2,
                "es_refuerzo": True,
            })

    calendario.sort(key=lambda x: x["fecha_programada"])
    return calendario


def proxima_dosis(vacuna_aplicada: Any) -> Optional[date]:
    """Calcula la fecha sugerida de la próxima dosis basada en el tipo de vacuna y especie."""
    tipo = getattr(vacuna_aplicada, "tipo", None) or (
        vacuna_aplicada.get("tipo") if isinstance(vacuna_aplicada, dict) else None
    )
    fecha_ap = getattr(vacuna_aplicada, "fecha_aplicacion", None) or (
        vacuna_aplicada.get("fecha_aplicacion") if isinstance(vacuna_aplicada, dict) else None
    )

    if not tipo or not fecha_ap:
        return None

    tipo_norm = str(tipo).strip().lower()

    # Buscar semanas de refuerzo en los calendarios
    for esp_reglas in CALENDARIO_VACUNAS.values():
        for item in esp_reglas:
            if item["vacuna"].lower() == tipo_norm:
                semanas = item.get("refuerzo_semanas", 52)
                return fecha_ap + timedelta(days=semanas * 7)

    # Si no está en el catálogo, por defecto 1 año (52 semanas)
    return fecha_ap + timedelta(days=365)


def vacunas_pendientes(paciente: Any, vacunas_aplicadas: List[Any]) -> List[dict]:
    """Compara el calendario teórico con las vacunas ya aplicadas y devuelve las pendientes o vencidas."""
    especie = getattr(paciente, "especie", None) or (
        paciente.get("especie") if isinstance(paciente, dict) else None
    )
    fecha_nac = getattr(paciente, "fecha_nacimiento", None) or (
        paciente.get("fecha_nacimiento") if isinstance(paciente, dict) else None
    )

    if not especie or not fecha_nac:
        return []

    calendario = calcular_calendario(especie, fecha_nac)
    aplicadas_tipos = set()
    for v in vacunas_aplicadas:
        t = getattr(v, "tipo", None) or (v.get("tipo") if isinstance(v, dict) else None)
        if t:
            aplicadas_tipos.add(str(t).strip().lower())

    pendientes = []
    hoy = date.today()
    for prog in calendario:
        t_prog = prog["vacuna"].lower()
        # Si la primera dosis no está registrada, o si es un refuerzo cuya fecha ya pasó
        if t_prog not in aplicadas_tipos or prog["fecha_programada"] <= hoy:
            estado = "vencida" if prog["fecha_programada"] < hoy else "pendiente"
            pendientes.append({
                **prog,
                "estado": estado,
                "dias_retraso": (hoy - prog["fecha_programada"]).days if prog["fecha_programada"] < hoy else 0,
            })

    return pendientes
