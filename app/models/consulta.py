"""Modelo SQLModel para la entidad Consulta (registro clínico)."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Consulta(SQLModel, table=True):
    """Registro de una atención médica.

    Los campos nota, indicaciones y diagnostico serán cifrados en el Módulo 9.
    Por ahora se almacenan como texto plano.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    consultorio_id: int = Field(foreign_key="consultorio.id")
    paciente_id: int = Field(foreign_key="paciente.id")
    profesional_id: int = Field(foreign_key="usuario.id")
    cita_id: Optional[int] = Field(default=None, foreign_key="cita.id")
    fecha: datetime
    motivo: str
    # Pendiente de cifrado en Módulo 9
    nota: str = Field(default="")
    indicaciones: str = Field(default="")
    diagnostico: Optional[str] = None
    proxima_cita: Optional[datetime] = None
    demo: bool = Field(default=False)
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Bloque 2: normalización de texto clínico
    medicamentos: Optional[str] = None       # lista separada por comas, normalizada
    diagnostico_codigo: Optional[str] = None  # código CIE-10 orientativo
