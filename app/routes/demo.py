"""Endpoints para el Modo Demo: cargar, borrar y consultar datos de ejemplo — Módulo 10."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.database import get_session
from app.dependencies import get_current_user
from app.models.usuario import Usuario
from app.services.demo import borrar_datos_demo, contar_datos_demo, generar_datos_demo

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/cargar", status_code=status.HTTP_201_CREATED)
def cargar_datos_demo(
    db: Session = Depends(get_session),
    usuario: Usuario = Depends(get_current_user),
) -> dict:
    """Genera datos de demostración (pacientes, citas, consultas, pagos).

    Solo accesible por el rol MEDICO.
    Todos los registros creados llevan demo=True.
    """
    if usuario.rol != "MEDICO":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el médico puede cargar datos de demo.",
        )

    conteos = generar_datos_demo(db, usuario.consultorio_id, usuario.id)
    return {"mensaje": "Datos de demo generados correctamente.", "generados": conteos}


@router.delete("/borrar", status_code=status.HTTP_200_OK)
def borrar_demo(
    db: Session = Depends(get_session),
    usuario: Usuario = Depends(get_current_user),
) -> dict:
    """Elimina SOLO los registros marcados con demo=True del consultorio.

    Solo accesible por el rol MEDICO.
    Nunca toca registros reales (demo=False).
    """
    if usuario.rol != "MEDICO":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el médico puede borrar datos de demo.",
        )

    eliminados = borrar_datos_demo(db, usuario.consultorio_id)
    return {"mensaje": "Datos de demo eliminados correctamente.", "eliminados": eliminados}


@router.get("/estado", status_code=status.HTTP_200_OK)
def estado_demo(
    db: Session = Depends(get_session),
    usuario: Usuario = Depends(get_current_user),
) -> dict:
    """Retorna el conteo actual de registros demo=True en el consultorio."""
    conteos = contar_datos_demo(db, usuario.consultorio_id)
    return {"demo_activo": conteos["total"] > 0, "conteos": conteos}
