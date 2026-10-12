"""Rutas de licencia — API JSON y vista HTML /licencia."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlmodel import Session

from app.config import FOUNDER_HARDWARE_IDS, es_founder as _es_founder_config
from app.database import get_session
from app.dependencies import get_current_user
from app.models.usuario import Usuario
from app.services.hardware import obtener_hardware_id
from app.services.licencia import (
    activar_licencia,
    info_licencia,
    renovar_mes,
    validar_formato_clave,
)

router = APIRouter(tags=["licencia"])
templates = Jinja2Templates(directory="app/templates")


# ── Schemas ───────────────────────────────────────────────────────────────────

class ActivarRequest(BaseModel):
    """Cuerpo para activar una licencia."""
    clave: str


# ── Vista HTML ─────────────────────────────────────────────────────────────────

@router.get("/licencia", response_class=HTMLResponse)
def vista_licencia(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> HTMLResponse:
    """Página de gestión de licencia del consultorio."""
    info = info_licencia(db)
    hw = obtener_hardware_id()
    return templates.TemplateResponse(
        "licencia/estado.html",
        {
            "request": request,
            "usuario": usuario,
            "info": info,
            "hardware_id": hw,
            "active_page": "licencia",
        },
    )


# ── API JSON ──────────────────────────────────────────────────────────────────

@router.get("/api/licencia/estado")
def api_estado(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict:
    """Devuelve el estado completo de la licencia."""
    return info_licencia(db)


@router.get("/api/licencia/hardware-id")
def api_hardware_id(
    usuario: Usuario = Depends(get_current_user),
) -> dict:
    """Devuelve el hardware_id de esta máquina."""
    return {"hardware_id": obtener_hardware_id()}


@router.post("/api/licencia/activar")
def api_activar(
    body: ActivarRequest,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict:
    """Activa la licencia con la clave proporcionada.

    Si el usuario es founder, la operación es ignorada y retorna estado=founder.
    """
    return activar_licencia(db, body.clave)


@router.post("/api/licencia/renovar")
def api_renovar(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict:
    """Extiende la licencia al último día del mes siguiente."""
    return renovar_mes(db)


@router.post("/api/licencia/registrar-founder")
def api_registrar_founder(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict:
    """Registra el hardware_id actual en la lista de founders (en memoria).

    Solo disponible si el usuario ya es founder por email.
    El cambio persiste en memoria hasta el próximo reinicio;
    para hacerlo permanente, copiar el hardware_id a config.py.
    """
    if not _es_founder_config(usuario.email or ""):
        return {"ok": False, "mensaje": "Solo el founder puede ejecutar esta acción."}

    hw = obtener_hardware_id()
    if hw not in FOUNDER_HARDWARE_IDS:
        FOUNDER_HARDWARE_IDS.append(hw)

    return {
        "ok": True,
        "hardware_id": hw,
        "mensaje": (
            f"Hardware registrado en memoria: {hw}\n"
            "Para hacerlo permanente, añádelo a FOUNDER_HARDWARE_IDS en app/config.py."
        ),
    }
