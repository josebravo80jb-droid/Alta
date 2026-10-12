"""Schemas Pydantic para citas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CitaCreate(BaseModel):
    """Datos necesarios para crear una nueva cita."""

    paciente_id: int
    fecha_hora: datetime
    duracion_min: int = 30
    motivo: Optional[str] = None


class CitaUpdate(BaseModel):
    """Campos actualizables de una cita (todos opcionales)."""

    fecha_hora: Optional[datetime] = None
    duracion_min: Optional[int] = None
    motivo: Optional[str] = None
    estado: Optional[str] = None


class CitaEstadoUpdate(BaseModel):
    """Payload para cambiar solo el estado de una cita."""

    estado: str  # pendiente | confirmada | completada | no_show | cancelada


class CitaResponse(BaseModel):
    """Representación pública de una cita con nombre del paciente."""

    id: int
    paciente_id: int
    paciente_nombre: str
    profesional_id: int
    fecha_hora: datetime
    duracion_min: int
    estado: str
    motivo: Optional[str]
    creado_en: datetime
