"""Endpoints de la API de consultas clínicas con control de acceso por rol — Módulo 7."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models.paciente import Paciente
from app.models.usuario import Usuario
from app.schemas.consulta import ConsultaCreate, ConsultaResponse, ConsultaUpdate
from app.services.auditoria import registrar as registrar_auditoria
from app.services.cifrado import descifrar
from app.services.consultas import (
    actualizar_consulta,
    crear_consulta,
    listar_consultas_paciente,
    obtener_consulta,
)

router = APIRouter(tags=["consultas"])


def _verificar_rol_medico(usuario: Usuario):
    """Lanza HTTP 403 Forbidden si el usuario no tiene rol MEDICO."""
    if usuario.rol != "MEDICO":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operación permitida únicamente para médicos",
        )


@router.post("/api/consultas", response_model=ConsultaResponse, status_code=status.HTTP_201_CREATED)
def ruta_crear_consulta(
    data: ConsultaCreate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ConsultaResponse:
    """Crea una nueva consulta médica. Solo disponible para profesionales con rol MEDICO."""
    _verificar_rol_medico(usuario)

    try:
        consulta = crear_consulta(db=db, data=data, usuario=usuario)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))

    registrar_auditoria(db, usuario.id, "CREATE", "consulta", consulta.id)

    paciente = db.get(Paciente, consulta.paciente_id)
    return ConsultaResponse(
        id=consulta.id,
        paciente_id=consulta.paciente_id,
        paciente_nombre=paciente.nombre if paciente else None,
        fecha=consulta.fecha,
        motivo=consulta.motivo,
        nota=descifrar(consulta.nota),
        indicaciones=descifrar(consulta.indicaciones),
        diagnostico=descifrar(consulta.diagnostico) if consulta.diagnostico else None,
        proxima_cita=consulta.proxima_cita,
        creado_en=consulta.creado_en,
        medico_nombre=usuario.nombre,
    )


@router.get("/api/consultas/{id}", response_model=ConsultaResponse)
def ruta_obtener_consulta(
    id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ConsultaResponse:
    """Obtiene el detalle completo de una consulta clínica. Solo disponible para rol MEDICO."""
    _verificar_rol_medico(usuario)

    consulta = obtener_consulta(db=db, consulta_id=id, consultorio_id=usuario.consultorio_id)
    if not consulta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta no encontrada")

    registrar_auditoria(db, usuario.id, "VIEW", "consulta", consulta.id)

    paciente = db.get(Paciente, consulta.paciente_id)
    medico = db.get(Usuario, consulta.profesional_id)
    return ConsultaResponse(
        id=consulta.id,
        paciente_id=consulta.paciente_id,
        paciente_nombre=paciente.nombre if paciente else None,
        fecha=consulta.fecha,
        motivo=consulta.motivo,
        nota=consulta.nota,
        indicaciones=consulta.indicaciones,
        diagnostico=consulta.diagnostico,
        proxima_cita=consulta.proxima_cita,
        creado_en=consulta.creado_en,
        medico_nombre=medico.nombre if medico else None,
    )


@router.get("/api/pacientes/{id}/consultas", response_model=list[ConsultaResponse])
def ruta_listar_consultas_paciente(
    id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> list[ConsultaResponse]:
    """Lista consultas de un paciente.

    Regla dura de permisos:
    Si el rol del usuario es ASISTENTE, no se envían campos clínicos confidenciales
    (nota, indicaciones, diagnostico).
    """
    paciente = db.exec(
        select(Paciente).where(
            Paciente.id == id,
            Paciente.consultorio_id == usuario.consultorio_id,
        )
    ).first()
    if not paciente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado")

    consultas = listar_consultas_paciente(db=db, paciente_id=id, consultorio_id=usuario.consultorio_id)

    # Cache de médicos para nombres
    medicos_map = {}
    resultado = []
    es_asistente = (usuario.rol == "ASISTENTE")

    for c in consultas:
        if c.profesional_id not in medicos_map:
            doc = db.get(Usuario, c.profesional_id)
            medicos_map[c.profesional_id] = doc.nombre if doc else None

        resultado.append(
            ConsultaResponse(
                id=c.id,
                paciente_id=c.paciente_id,
                paciente_nombre=paciente.nombre,
                fecha=c.fecha,
                motivo=c.motivo,
                # ASISTENTE no recibe datos clínicos privados
                nota=None if es_asistente else c.nota,
                indicaciones=None if es_asistente else c.indicaciones,
                diagnostico=None if es_asistente else c.diagnostico,
                proxima_cita=c.proxima_cita,
                creado_en=c.creado_en,
                medico_nombre=medicos_map[c.profesional_id],
            )
        )

    return resultado


@router.put("/api/consultas/{id}", response_model=ConsultaResponse)
def ruta_actualizar_consulta(
    id: int,
    data: ConsultaUpdate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ConsultaResponse:
    """Actualiza una consulta médica existente. Solo disponible para rol MEDICO."""
    _verificar_rol_medico(usuario)

    consulta = actualizar_consulta(db=db, consulta_id=id, data=data, consultorio_id=usuario.consultorio_id)
    if not consulta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta no encontrada")

    registrar_auditoria(db, usuario.id, "UPDATE", "consulta", consulta.id)

    paciente = db.get(Paciente, consulta.paciente_id)
    medico = db.get(Usuario, consulta.profesional_id)
    return ConsultaResponse(
        id=consulta.id,
        paciente_id=consulta.paciente_id,
        paciente_nombre=paciente.nombre if paciente else None,
        fecha=consulta.fecha,
        motivo=consulta.motivo,
        nota=consulta.nota,
        indicaciones=consulta.indicaciones,
        diagnostico=consulta.diagnostico,
        proxima_cita=consulta.proxima_cita,
        creado_en=consulta.creado_en,
        medico_nombre=medico.nombre if medico else None,
    )

