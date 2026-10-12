"""Endpoints de la API de pacientes y dueños — Módulo 6."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.database import get_session
from app.dependencies import get_current_user
from app.models.usuario import Usuario
from app.schemas.paciente import (
    DuenoCreate,
    DuenoResponse,
    PacienteCreate,
    PacienteDetalle,
    PacienteResponse,
    PacienteUpdate,
)
from app.services.pacientes import (
    actualizar_paciente,
    buscar_duenos,
    buscar_pacientes,
    crear_dueno,
    crear_paciente_completo,
    eliminar_paciente,
    obtener_paciente_detalle,
)

router = APIRouter(tags=["pacientes"])


# ── Rutas de Dueños ───────────────────────────────────────────────────────────

@router.post("/api/duenos", response_model=DuenoResponse, status_code=status.HTTP_201_CREATED)
def ruta_crear_dueno(
    data: DuenoCreate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> DuenoResponse:
    """Registra un nuevo dueño de mascota para el consultorio."""
    dueno = crear_dueno(db=db, data=data, consultorio_id=usuario.consultorio_id)
    return DuenoResponse(
        id=dueno.id,
        consultorio_id=dueno.consultorio_id,
        nombre=dueno.nombre,
        cedula=dueno.cedula,
        telefono=dueno.telefono,
        email=dueno.email,
        direccion=dueno.direccion,
        creado_en=dueno.creado_en,
    )


@router.get("/api/duenos", response_model=list[DuenoResponse])
def ruta_listar_duenos(
    q: str = "",
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> list[DuenoResponse]:
    """Lista dueños con búsqueda opcional."""
    duenos = buscar_duenos(db=db, consultorio_id=usuario.consultorio_id, q=q)
    return [
        DuenoResponse(
            id=d.id,
            consultorio_id=d.consultorio_id,
            nombre=d.nombre,
            cedula=d.cedula,
            telefono=d.telefono,
            email=d.email,
            direccion=d.direccion,
            creado_en=d.creado_en,
        )
        for d in duenos
    ]


# ── Rutas de Pacientes ────────────────────────────────────────────────────────

@router.get("/api/pacientes", response_model=list[PacienteResponse])
def ruta_listar_pacientes(
    q: str = "",
    tipo: Optional[str] = Query(None, description="HUMANO o MASCOTA"),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> list[PacienteResponse]:
    """Lista pacientes del consultorio filtrados por búsqueda o tipo."""
    pacientes = buscar_pacientes(db=db, consultorio_id=usuario.consultorio_id, q=q, tipo=tipo)
    return [PacienteResponse(**p) for p in pacientes]


@router.post("/api/pacientes", response_model=PacienteResponse, status_code=status.HTTP_201_CREATED)
def ruta_crear_paciente(
    data: PacienteCreate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> PacienteResponse:
    """Crea un nuevo paciente con todos sus datos."""
    paciente = crear_paciente_completo(db=db, data=data, usuario=usuario)
    from app.services.auditoria import registrar as registrar_auditoria
    registrar_auditoria(db, usuario.id, "CREATE", "paciente", paciente.id)
    return PacienteResponse(
        id=paciente.id,
        nombre=paciente.nombre,
        telefono=paciente.telefono,
        email=paciente.email,
        cedula=paciente.cedula,
        tipo=paciente.tipo,
        fecha_nacimiento=paciente.fecha_nacimiento,
        alergias=paciente.alergias,
        notas_generales=paciente.notas_generales,
        especie=paciente.especie,
        raza=paciente.raza,
        peso_kg=paciente.peso_kg,
        microchip=paciente.microchip,
        dueno_id=paciente.dueno_id,
        creado_en=paciente.creado_en,
        ultima_visita=None,
    )


@router.get("/api/pacientes/{id}", response_model=PacienteResponse)
def ruta_obtener_paciente(
    id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> PacienteResponse:
    """Devuelve los datos de un paciente."""
    detalle = obtener_paciente_detalle(db=db, paciente_id=id, consultorio_id=usuario.consultorio_id)
    if not detalle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado")
    return PacienteResponse(**detalle["paciente"])


@router.put("/api/pacientes/{id}", response_model=PacienteResponse)
def ruta_actualizar_paciente(
    id: int,
    data: PacienteUpdate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> PacienteResponse:
    """Actualiza la información de un paciente."""
    paciente = actualizar_paciente(db=db, paciente_id=id, data=data, consultorio_id=usuario.consultorio_id)
    if not paciente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado")

    from app.services.auditoria import registrar as registrar_auditoria
    registrar_auditoria(db, usuario.id, "UPDATE", "paciente", paciente.id)

    return PacienteResponse(
        id=paciente.id,
        nombre=paciente.nombre,
        telefono=paciente.telefono,
        email=paciente.email,
        cedula=paciente.cedula,
        tipo=paciente.tipo,
        fecha_nacimiento=paciente.fecha_nacimiento,
        alergias=paciente.alergias,
        notas_generales=paciente.notas_generales,
        especie=paciente.especie,
        raza=paciente.raza,
        peso_kg=paciente.peso_kg,
        microchip=paciente.microchip,
        dueno_id=paciente.dueno_id,
        creado_en=paciente.creado_en,
    )


@router.delete("/api/pacientes/{id}", status_code=status.HTTP_200_OK)
def ruta_eliminar_paciente(
    id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict[str, str]:
    """Elimina un paciente (físico o soft delete si tiene historial)."""
    ok = eliminar_paciente(db=db, paciente_id=id, consultorio_id=usuario.consultorio_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado")

    from app.services.auditoria import registrar as registrar_auditoria
    registrar_auditoria(db, usuario.id, "DELETE", "paciente", id)

    return {"mensaje": "Paciente eliminado exitosamente"}


@router.get("/api/pacientes/{id}/historial", response_model=PacienteDetalle)
def ruta_obtener_historial(
    id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> PacienteDetalle:
    """Devuelve la ficha completa del paciente con su historial clínico y dueño."""
    detalle = obtener_paciente_detalle(db=db, paciente_id=id, consultorio_id=usuario.consultorio_id, usuario=usuario)
    if not detalle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado")
    return PacienteDetalle(**detalle)
