"""Modelo SQLModel para la entidad Vacuna."""

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Vacuna(SQLModel, table=True):
    """Registro de vacunas administradas a pacientes (mascotas)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    paciente_id: int = Field(foreign_key="paciente.id")
    consultorio_id: int = Field(foreign_key="consultorio.id")
    tipo: str  # "rabia", "moquillo", etc.
    fecha_aplicacion: date
    proxima_dosis: Optional[date] = None
    lote: Optional[str] = None
    laboratorio: Optional[str] = None
    aplicada_por: int = Field(foreign_key="usuario.id")
    notas: Optional[str] = None
    demo: bool = Field(default=False)
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
