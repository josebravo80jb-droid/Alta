"""Modelo SQLModel para la entidad Pago."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Pago(SQLModel, table=True):
    """Registro de un pago asociado a una consulta o paciente."""

    id: Optional[int] = Field(default=None, primary_key=True)
    consultorio_id: int = Field(foreign_key="consultorio.id")
    paciente_id: int = Field(foreign_key="paciente.id")
    consulta_id: Optional[int] = Field(default=None, foreign_key="consulta.id")
    monto: float
    moneda: str = Field(default="USD")
    metodo: Optional[str] = None  # efectivo, tarjeta, transferencia, etc.
    # Estados válidos: pagado | pendiente
    estado: str = Field(default="pagado")
    fecha: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    registrado_por: int = Field(foreign_key="usuario.id")
    tasa_bcv_aplicada: Optional[float] = None
    demo: bool = Field(default=False)
