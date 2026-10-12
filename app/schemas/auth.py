"""Schemas Pydantic para autenticación y registro."""

from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator
from app.services.validacion import normalizar_rif, validar_rif_ve


class RegistroRequest(BaseModel):
    """Datos necesarios para registrar un nuevo consultorio y su médico titular."""

    nombre: str
    email: EmailStr
    password: str
    especialidad: str
    direccion: str
    telefono: str
    rif: Optional[str] = None
    tipo: str = "MEDICO"
    horario_apertura: str = "08:00"
    horario_cierre: str = "18:00"
    duracion_cita: int = 30
    precio_consulta: float = 0.0

    @field_validator("rif")
    @classmethod
    def validar_rif(cls, v: Optional[str]) -> Optional[str]:
        if v:
            v_limpio = v.strip()
            if v_limpio:
                if not validar_rif_ve(v_limpio):
                    raise ValueError("RIF venezolano inválido (ejemplo: J-12345678-9)")
                return normalizar_rif(v_limpio)
        return v


class LoginRequest(BaseModel):
    """Credenciales de acceso."""

    email: EmailStr
    password: str


class UsuarioResponse(BaseModel):
    """Datos públicos del usuario devueltos en el token."""

    id: int
    nombre: str
    email: str
    rol: str
    tipo_consultorio: str = "MEDICO"


class TokenResponse(BaseModel):
    """Respuesta JWT tras registro o login exitoso."""

    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse
    tipo_consultorio: str = "MEDICO"
