"""Modelo SQLModel para la entidad Dueno (propietario de mascota)."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Dueno(SQLModel, table=True):
    """Propietario de una mascota registrado en el consultorio."""

    id: Optional[int] = Field(default=None, primary_key=True)
    consultorio_id: int = Field(foreign_key="consultorio.id")
    nombre: str
    cedula: Optional[str] = None
    telefono: str
    email: Optional[str] = None
    direccion: Optional[str] = None
    demo: bool = Field(default=False)
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
