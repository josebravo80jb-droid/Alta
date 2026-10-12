"""Modelo SQLModel para la configuración de un consultorio."""

from typing import Optional

from sqlmodel import Field, SQLModel


class Configuracion(SQLModel, table=True):
    """Configuración operativa de un consultorio (1:1 con Consultorio)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    consultorio_id: int = Field(foreign_key="consultorio.id", unique=True)
    horario_apertura: str = Field(default="08:00")   # HH:MM
    horario_cierre: str = Field(default="18:00")     # HH:MM
    dias_laborables: str = Field(default="LUN,MAR,MIE,JUE,VIE")
    duracion_cita_default: int = Field(default=30)   # minutos
    precio_consulta_default: float = Field(default=0.0)
    moneda_default: str = Field(default="USD")
    tasa_respaldo: float = Field(default=40.0)
