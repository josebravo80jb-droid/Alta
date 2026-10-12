"""Schemas Pydantic para el módulo de consultas clínicas — Módulo 7."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ConsultaCreate(BaseModel):
    """Datos necesarios para crear una nueva consulta médica."""

    paciente_id: int
    cita_id: Optional[int] = None
    motivo: str
    nota: str
    indicaciones: Optional[str] = ""
    diagnostico: Optional[str] = None
    proxima_cita: Optional[datetime] = None


class ConsultaUpdate(BaseModel):
    """Datos opcionales para actualizar una consulta clínica."""

    cita_id: Optional[int] = None
    motivo: Optional[str] = None
    nota: Optional[str] = None
    indicaciones: Optional[str] = None
    diagnostico: Optional[str] = None
    proxima_cita: Optional[datetime] = None


class ConsultaResponse(BaseModel):
    """Representación pública de una consulta clínica.

    Los campos clínicos sensibles (nota, indicaciones, diagnostico) son opcionales
    y deben omitirse o ser None para usuarios con rol ASISTENTE.
    """

    id: int
    paciente_id: int
    paciente_nombre: Optional[str] = None
    fecha: datetime
    motivo: str
    nota: Optional[str] = None
    indicaciones: Optional[str] = None
    diagnostico: Optional[str] = None
    proxima_cita: Optional[datetime] = None
    creado_en: datetime
    medico_nombre: Optional[str] = None
