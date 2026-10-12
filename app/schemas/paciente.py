"""Schemas Pydantic para pacientes y dueños — Módulo 6."""

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator
from app.services.validacion import normalizar_cedula, validar_cedula_ve


class DuenoCreate(BaseModel):
    """Datos para crear un nuevo dueño de mascota."""

    nombre: str
    cedula: Optional[str] = None
    telefono: str
    email: Optional[str] = None
    direccion: Optional[str] = None


class DuenoResponse(BaseModel):
    """Representación de un dueño."""

    id: int
    consultorio_id: int
    nombre: str
    cedula: Optional[str] = None
    telefono: str
    email: Optional[str] = None
    direccion: Optional[str] = None
    creado_en: datetime


class PacienteCreate(BaseModel):
    """Datos completos para crear un paciente."""

    nombre: str
    telefono: Optional[str] = None
    email: Optional[str] = None
    cedula: Optional[str] = None
    tipo: str = "HUMANO"  # "HUMANO" | "MASCOTA"
    fecha_nacimiento: Optional[date] = None
    alergias: Optional[str] = None
    notas_generales: Optional[str] = None

    # Antecedentes clínicos (solo HUMANO)
    peso_kg_humano: Optional[float] = None
    es_diabetico: bool = False
    tiene_hipertension: bool = False
    esta_embarazada: bool = False
    toma_anticoagulantes: bool = False

    # Específico para MASCOTA
    especie: Optional[str] = None
    raza: Optional[str] = None
    peso_kg: Optional[float] = None
    microchip: Optional[str] = None
    dueno_id: Optional[int] = None

    @field_validator("cedula")
    @classmethod
    def validar_cedula(cls, v: Optional[str]) -> Optional[str]:
        if v:
            v_limpio = v.strip()
            if v_limpio:
                if not validar_cedula_ve(v_limpio):
                    raise ValueError("Cédula venezolana inválida (formato: V-12345678 o 6-9 dígitos)")
                return normalizar_cedula(v_limpio)
        return v


class PacienteUpdate(BaseModel):
    """Datos opcionales para actualizar un paciente."""

    nombre: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    cedula: Optional[str] = None
    tipo: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    alergias: Optional[str] = None
    notas_generales: Optional[str] = None

    peso_kg_humano: Optional[float] = None
    es_diabetico: Optional[bool] = None
    tiene_hipertension: Optional[bool] = None
    esta_embarazada: Optional[bool] = None
    toma_anticoagulantes: Optional[bool] = None

    especie: Optional[str] = None
    raza: Optional[str] = None
    peso_kg: Optional[float] = None
    microchip: Optional[str] = None
    dueno_id: Optional[int] = None


class PacienteResponse(BaseModel):
    """Representación pública estándar de un paciente."""

    id: int
    nombre: str
    telefono: Optional[str] = None
    email: Optional[str] = None
    cedula: Optional[str] = None
    tipo: str
    fecha_nacimiento: Optional[date] = None
    alergias: Optional[str] = None
    notas_generales: Optional[str] = None
    peso_kg_humano: Optional[float] = None
    es_diabetico: Optional[bool] = None
    tiene_hipertension: Optional[bool] = None
    esta_embarazada: Optional[bool] = None
    toma_anticoagulantes: Optional[bool] = None
    especie: Optional[str] = None
    raza: Optional[str] = None
    peso_kg: Optional[float] = None
    microchip: Optional[str] = None
    dueno_id: Optional[int] = None
    creado_en: Optional[datetime] = None
    ultima_visita: Optional[datetime] = None


class PacienteDetalle(BaseModel):
    """Ficha completa del paciente incluyendo historial y datos del dueño."""

    paciente: PacienteResponse
    dueno: Optional[DuenoResponse] = None
    historial: dict[str, list[Any]] = {
        "citas": [],
        "consultas": [],
        "pagos": [],
    }
