"""Modelo SQLModel para la licencia local de Alta.

Una sola fila (id=1) por instalación.
No hay tabla de servidores externos — todo local.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class LicenciaLocal(SQLModel, table=True):
    """Registro de licencia local. Siempre hay exactamente una fila (id=1).

    Estados válidos:
        trial    — período de prueba (30 días desde instalación)
        activa   — clave activada, dentro de vigencia
        gracia   — vencida hace ≤7 días, solo lectura permitida
        expirada — vencida hace >7 días, solo lectura
        bloqueada — hardware_id no coincide (anticopia)
        founder  — usuario con acceso permanente, sin licencia requerida
    """

    id: int = Field(default=1, primary_key=True)
    clave: Optional[str] = None
    estado: str = Field(default="trial")
    fecha_instalacion: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    fecha_expiracion_trial: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)  # se fija en iniciar_si_no_existe
    )
    hardware_id: str = Field(default="")
    activa_desde: Optional[datetime] = None
    activa_hasta: Optional[datetime] = None
    precio_mensual: float = Field(default=50.0)
    monto_prorrateado: Optional[float] = None
    es_founder: bool = Field(default=False)
    intentos_fallidos: int = Field(default=0)
