"""Modelo SQLModel para la entidad Consultorio."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Consultorio(SQLModel, table=True):
    """Representa un consultorio médico registrado en el sistema."""

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(index=True)
    tipo: str = Field(default="MEDICO")
    direccion: str
    telefono: str
    rif: Optional[str] = None
    # Agenda pública
    slug: Optional[str] = Field(default=None, unique=True, index=True)
    agenda_publica_activa: bool = Field(default=False)
    duracion_cita_publica: int = Field(default=30)
    telefono_whatsapp_publico: Optional[str] = None
    bio_publica: Optional[str] = None
    horario_publico: Optional[str] = Field(default=None)
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
