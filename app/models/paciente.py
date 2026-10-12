"""Modelo SQLModel para la entidad Paciente (humano o mascota)."""

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Paciente(SQLModel, table=True):
    """Paciente del consultorio.

    El campo `tipo` determina si es HUMANO o MASCOTA.
    Los campos especie/raza/peso_kg/microchip/dueno_id solo aplican a mascotas.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    consultorio_id: int = Field(foreign_key="consultorio.id")
    tipo: str = Field(default="HUMANO")  # "HUMANO" | "MASCOTA"

    # Datos comunes
    nombre: str
    telefono: Optional[str] = None
    email: Optional[str] = None
    notas_generales: Optional[str] = None
    cedula: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    alergias: Optional[str] = None
    demo: bool = Field(default=False)
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Antecedentes clínicos (solo HUMANO)
    peso_kg_humano: Optional[float] = None  # peso del paciente humano en kg
    es_diabetico: bool = Field(default=False)
    tiene_hipertension: bool = Field(default=False)
    esta_embarazada: bool = Field(default=False)
    toma_anticoagulantes: bool = Field(default=False)

    # Datos exclusivos de mascotas
    especie: Optional[str] = None
    raza: Optional[str] = None
    peso_kg: Optional[float] = None
    microchip: Optional[str] = None
    dueno_id: Optional[int] = Field(default=None, foreign_key="dueno.id")
