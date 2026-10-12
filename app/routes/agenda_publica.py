"""Rutas públicas para la Agenda Pública (sin autenticación requerida)."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.database import get_session
from app.models.consultorio import Consultorio
from app.services.agenda_publica import (
    obtener_slots_disponibles,
    reservar_cita_publica,
    solicitar_horario_libre,
)

router = APIRouter(prefix="/api/agenda-publica", tags=["agenda-publica"])


class ReservarRequest(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    telefono: str = Field(..., min_length=7, max_length=20)
    motivo: str = Field(..., min_length=3, max_length=500)
    fecha: str
    hora: str


class SolicitarRequest(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    telefono: str = Field(..., min_length=7, max_length=20)
    motivo: str = Field(..., min_length=3, max_length=500)
    fecha_preferida: Optional[str] = None
    hora_preferida: Optional[str] = None


def _obtener_ip(request: Request) -> str:
    """Extrae la IP real considerando proxies y Cloudflare."""
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    x_forwarded = request.headers.get("X-Forwarded-For")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


@router.get("/{slug}")
def api_info_consultorio(slug: str, db: Session = Depends(get_session)):
    """Devuelve los datos públicos del consultorio."""
    consultorio = db.exec(select(Consultorio).where(Consultorio.slug == slug)).first()
    if not consultorio or not consultorio.agenda_publica_activa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultorio no encontrado o agenda pública deshabilitada.",
        )

    return {
        "nombre": consultorio.nombre,
        "tipo": consultorio.tipo,
        "especialidad": "Veterinaria" if consultorio.tipo == "VETERINARIO" else "Medicina General",
        "bio": consultorio.bio_publica or "",
        "telefono": consultorio.telefono_whatsapp_publico or consultorio.telefono,
        "direccion": consultorio.direccion,
        "duracion_cita": consultorio.duracion_cita_publica or 30,
    }


@router.get("/{slug}/disponibles")
def api_slots_disponibles(slug: str, db: Session = Depends(get_session)):
    """Devuelve los slots disponibles para los próximos 7 días."""
    consultorio = db.exec(select(Consultorio).where(Consultorio.slug == slug)).first()
    if not consultorio or not consultorio.agenda_publica_activa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultorio no encontrado o agenda pública inactiva.",
        )

    slots = obtener_slots_disponibles(db, consultorio.id, dias=7)
    return {"slots": slots}


@router.post("/{slug}/reservar")
def api_reservar(
    slug: str,
    body: ReservarRequest,
    request: Request,
    db: Session = Depends(get_session),
):
    """Reserva una cita desde la agenda pública."""
    ip = _obtener_ip(request)
    try:
        resultado = reservar_cita_publica(db, slug, body.dict(), ip=ip)
        return resultado
    except ValueError as e:
        msg = str(e)
        if "Límite de solicitudes" in msg:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


@router.post("/{slug}/solicitar")
def api_solicitar(
    slug: str,
    body: SolicitarRequest,
    request: Request,
    db: Session = Depends(get_session),
):
    """Crea una solicitud de horario libre (fallback)."""
    ip = _obtener_ip(request)
    try:
        resultado = solicitar_horario_libre(db, slug, body.dict(), ip=ip)
        return resultado
    except ValueError as e:
        msg = str(e)
        if "Límite de solicitudes" in msg:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
