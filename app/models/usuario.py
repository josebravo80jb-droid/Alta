"""Modelo SQLModel para la entidad Usuario."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Usuario(SQLModel, table=True):
    """Representa un usuario del sistema (médico o asistente)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    consultorio_id: int = Field(foreign_key="consultorio.id")
    email: str = Field(unique=True, index=True)
    password_hash: str
    nombre: str
    rol: str = Field(default="MEDICO")  # "MEDICO" | "ASISTENTE"
    activo: bool = Field(default=True)
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def tipo_consultorio(self) -> str:
        """Devuelve el tipo de consultorio o MEDICO por defecto si se adjuntó."""
        return getattr(self, "_tipo_consultorio", "MEDICO")

    @tipo_consultorio.setter
    def tipo_consultorio(self, val: str):
        self._tipo_consultorio = val
