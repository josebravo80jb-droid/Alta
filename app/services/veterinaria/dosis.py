"""Cálculo orientativo de dosis veterinarias por peso corporal — AltaPet."""

from typing import List

# Dosis estándar orientativas (mg por kg)
DOSIS_ESTANDAR = {
    # Analgésicos
    "meloxicam": {"mg_por_kg": 0.1, "via": "oral", "frecuencia": "cada 24h"},
    "carprofeno": {"mg_por_kg": 2.2, "via": "oral", "frecuencia": "cada 12h"},
    "tramadol": {"mg_por_kg": 2.0, "via": "oral", "frecuencia": "cada 8-12h"},
    # Antibióticos
    "amoxicilina": {"mg_por_kg": 10.0, "via": "oral", "frecuencia": "cada 12h"},
    "enrofloxacina": {"mg_por_kg": 5.0, "via": "oral", "frecuencia": "cada 24h"},
    "metronidazol": {"mg_por_kg": 10.0, "via": "oral", "frecuencia": "cada 12h"},
    "cefalexina": {"mg_por_kg": 15.0, "via": "oral", "frecuencia": "cada 12h"},
    # Antiparasitarios
    "praziquantel": {"mg_por_kg": 5.0, "via": "oral", "frecuencia": "dosis única"},
    "ivermectina": {"mg_por_kg": 0.2, "via": "oral", "frecuencia": "cada 30 días"},
    "fenbendazol": {"mg_por_kg": 50.0, "via": "oral", "frecuencia": "cada 24h x 3 días"},
    # Antiinflamatorios
    "dexametasona": {"mg_por_kg": 0.2, "via": "inyectable", "frecuencia": "cada 24h"},
    "prednisona": {"mg_por_kg": 0.5, "via": "oral", "frecuencia": "cada 24h"},
}

ADVERTENCIA_LEGAL = "Cálculo orientativo. El veterinario debe validar antes de prescribir."


def listar_medicamentos() -> List[str]:
    """Devuelve la lista ordenada de medicamentos disponibles para dosificación."""
    return sorted(list(DOSIS_ESTANDAR.keys()))


def calcular_dosis(medicamento: str, peso_kg: float) -> dict:
    """Calcula la dosis en miligramos basada en el peso del paciente y posología de referencia.

    Fórmula: dosis_total_mg = peso_kg * mg_por_kg
    Lanza ValueError si el medicamento no existe o si el peso es menor o igual a cero.
    """
    if not medicamento:
        raise ValueError("Medicamento requerido")
    med_norm = str(medicamento).strip().lower()
    if med_norm not in DOSIS_ESTANDAR:
        raise ValueError(f"Medicamento '{medicamento}' no encontrado en el vademécum")

    peso = float(peso_kg)
    if peso <= 0:
        raise ValueError("El peso debe ser mayor a 0 kg")

    info = DOSIS_ESTANDAR[med_norm]
    dosis_mg = round(peso * info["mg_por_kg"], 2)

    return {
        "medicamento": med_norm,
        "peso_kg": peso,
        "dosis_mg": dosis_mg,
        "via": info["via"],
        "frecuencia": info["frecuencia"],
        "advertencia": ADVERTENCIA_LEGAL,
    }


def calcular_dosis_con_concentracion(
    medicamento: str,
    peso_kg: float,
    concentracion_mg_ml: float,
) -> dict:
    """Calcula tanto la dosis en mg como el volumen requerido en ml según la concentración."""
    resultado = calcular_dosis(medicamento, peso_kg)
    conc = float(concentracion_mg_ml)
    if conc <= 0:
        raise ValueError("La concentración debe ser mayor a 0 mg/ml")

    volumen_ml = round(resultado["dosis_mg"] / conc, 2)
    resultado["concentracion_mg_ml"] = conc
    resultado["volumen_ml"] = volumen_ml
    return resultado
