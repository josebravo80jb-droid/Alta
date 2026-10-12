"""Modelo SQLModel para la entidad Auditoria (log inmutable de acciones)."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Auditoria(SQLModel, table=True):
    """Registro de auditoría de acciones sobre entidades del sistema.

    hash_anterior y hash_actual permiten verificar integridad de los datos.
    Acciones válidas: CREATE, UPDATE, DELETE, VIEW.
    Entidades válidas: paciente, cita, consulta, pago.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id")
    accion: str                  # CREATE | UPDATE | DELETE | VIEW
    entidad: str                 # paciente | cita | consulta | pago
    entidad_id: int
    hash_anterior: str = Field(default="")
    hash_actual: str = Field(default="")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
