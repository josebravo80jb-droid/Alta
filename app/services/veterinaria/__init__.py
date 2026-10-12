"""Módulo de lógica veterinaria para AltaPet."""

from app.services.veterinaria.especies import listar_especies, obtener_especie
from app.services.veterinaria.razas import es_raza_valida, listar_razas
from app.services.veterinaria.vacunas import (
    calcular_calendario,
    proxima_dosis,
    vacunas_pendientes,
)
from app.services.veterinaria.dosis import (
    calcular_dosis,
    calcular_dosis_con_concentracion,
    listar_medicamentos,
)
from app.services.veterinaria.recordatorios import (
    generar_mensaje_recordatorio,
    vacunas_proximas_7_dias,
    vacunas_vencidas,
)

__all__ = [
    "listar_especies",
    "obtener_especie",
    "listar_razas",
    "es_raza_valida",
    "calcular_calendario",
    "proxima_dosis",
    "vacunas_pendientes",
    "calcular_dosis",
    "calcular_dosis_con_concentracion",
    "listar_medicamentos",
    "generar_mensaje_recordatorio",
    "vacunas_proximas_7_dias",
    "vacunas_vencidas",
]
