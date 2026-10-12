"""Schemas Pydantic para el módulo de pagos e ingresos — Módulo 8."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PagoCreate(BaseModel):
    """Datos necesarios para registrar un nuevo pago."""

    paciente_id: int
    consulta_id: Optional[int] = None
    monto: float
    moneda: str = "USD"
    metodo: Optional[str] = "efectivo"
    estado: str = "pagado"  # "pagado" | "pendiente"


class PagoUpdate(BaseModel):
    """Datos opcionales para actualizar un pago."""

    paciente_id: Optional[int] = None
    consulta_id: Optional[int] = None
    monto: Optional[float] = None
    moneda: Optional[str] = None
    metodo: Optional[str] = None
    estado: Optional[str] = None


class PagoResponse(BaseModel):
    """Representación pública de un pago registrado."""

    id: int
    paciente_id: int
    paciente_nombre: Optional[str] = None
    consulta_id: Optional[int] = None
    monto: float
    moneda: str
    metodo: Optional[str] = None
    estado: str
    fecha: datetime
    tasa_bcv_aplicada: Optional[float] = None
    registrado_por_nombre: Optional[str] = None
