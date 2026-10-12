"""Rutas de Reportes — GET /reportes y API /api/reportes."""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.database import get_session
from app.dependencies import get_current_user
from app.models.consultorio import Consultorio
from app.models.usuario import Usuario
from app.services.reportes import generar_reporte, kpi_financiero, kpi_demografico, kpi_clinico

router = APIRouter(tags=["reportes"])

templates = Jinja2Templates(directory="app/templates")

PERIODOS_VALIDOS = {"hoy", "semana", "mes", "año"}


# ---------------------------------------------------------------------------
# Vista HTML
# ---------------------------------------------------------------------------

@router.get("/reportes", response_class=HTMLResponse)
def vista_reportes(
    request: Request,
    periodo: str = Query(default="mes"),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> HTMLResponse:
    """Página principal de reportes con KPIs y gráficos."""
    if periodo not in PERIODOS_VALIDOS:
        periodo = "mes"

    reporte = generar_reporte(db, usuario.consultorio_id, periodo)
    consultorio = db.get(Consultorio, usuario.consultorio_id)

    return templates.TemplateResponse(
        request,
        "reportes/index.html",
        {
            "usuario": usuario,
            "consultorio": consultorio,
            "reporte": reporte,
            "periodo": periodo,
            "periodos": ["hoy", "semana", "mes", "año"],
        },
    )


# ---------------------------------------------------------------------------
# API JSON
# ---------------------------------------------------------------------------

@router.get("/api/reportes/completo")
def api_reporte_completo(
    periodo: str = Query(default="mes"),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict:
    """Devuelve el reporte completo en JSON."""
    if periodo not in PERIODOS_VALIDOS:
        periodo = "mes"
    return generar_reporte(db, usuario.consultorio_id, periodo)


@router.get("/api/reportes/financiero")
def api_financiero(
    periodo: str = Query(default="mes"),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict:
    """KPIs financieros del período."""
    if periodo not in PERIODOS_VALIDOS:
        periodo = "mes"
    return kpi_financiero(db, usuario.consultorio_id, periodo)


@router.get("/api/reportes/demografico")
def api_demografico(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict:
    """KPIs demográficos del consultorio."""
    return kpi_demografico(db, usuario.consultorio_id)


@router.get("/api/reportes/clinico")
def api_clinico(
    periodo: str = Query(default="mes"),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict:
    """KPIs clínicos del período."""
    if periodo not in PERIODOS_VALIDOS:
        periodo = "mes"
    return kpi_clinico(db, usuario.consultorio_id, periodo)
