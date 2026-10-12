"""Modelo SQLModel para la entidad Cita (turno/appointment)."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Cita(SQLModel, table=True):
    """Turno agendado para un paciente con un profesional del consultorio."""

    id: Optional[int] = Field(default=None, primary_key=True)
    consultorio_id: int = Field(foreign_key="consultorio.id")
    paciente_id: Optional[int] = Field(default=None, foreign_key="paciente.id")
    profesional_id: int = Field(foreign_key="usuario.id")
    fecha_hora: datetime
    duracion_min: int = Field(default=30)
    # Estados válidos: pendiente | confirmada | completada | no_show | cancelada
    estado: str = Field(default="pendiente")
    motivo: Optional[str] = None
    creada_por: int = Field(foreign_key="usuario.id")
    # Agenda pública
    origen: str = Field(default="interno")  # "interno" | "publico" | "solicitud"
    nombre_solicitante: Optional[str] = None
    telefono_solicitante: Optional[str] = None
    demo: bool = Field(default=False)
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
