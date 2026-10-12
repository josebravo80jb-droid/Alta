"""Schemas Pydantic para el dashboard (resumen del día)."""

from datetime import datetime

from pydantic import BaseModel


class CitaResumen(BaseModel):
    """Datos mínimos de una cita para mostrar en el dashboard."""

    id: int
    paciente_nombre: str
    fecha_hora: datetime
    motivo: str | None
    estado: str


class ResumenDashboard(BaseModel):
    """Métricas del día y del mes para el dashboard principal."""

    citas_hoy: int
    citas_pendientes: int
    citas_completadas: int
    ingresos_hoy: float
    ingresos_mes: float
    total_pacientes: int
    proximas_citas: list[CitaResumen]
