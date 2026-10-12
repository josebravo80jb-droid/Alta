"""Endpoints de la API de agenda y citas."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models.cita import Cita
from app.models.paciente import Paciente
from app.models.usuario import Usuario
from app.schemas.cita import CitaCreate, CitaEstadoUpdate, CitaResponse, CitaUpdate
from app.services.agenda import crear_cita, obtener_citas_semana, validar_disponibilidad

router = APIRouter(tags=["agenda"])

_ESTADOS_VALIDOS = {"pendiente", "confirmada", "completada", "no_show", "cancelada"}


def _cita_response(cita: Cita, paciente_nombre: str) -> CitaResponse:
    """Construye un CitaResponse enriquecido con el nombre del paciente."""
    return CitaResponse(
        id=cita.id,
        paciente_id=cita.paciente_id,
        paciente_nombre=paciente_nombre,
        profesional_id=cita.profesional_id,
        fecha_hora=cita.fecha_hora,
        duracion_min=cita.duracion_min,
        estado=cita.estado,
        motivo=cita.motivo,
        creado_en=cita.creado_en,
    )


def _get_cita_del_consultorio(
    cita_id: int,
    consultorio_id: int,
    db: Session,
) -> Cita:
    """Busca una cita por ID y valida que pertenezca al consultorio. Lanza 404 si no."""
    cita = db.get(Cita, cita_id)
    if not cita or cita.consultorio_id != consultorio_id:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    return cita


# ── GET /api/agenda/semana ────────────────────────────────────────────────────

@router.get("/api/agenda/semana", response_model=list[CitaResponse])
def semana(
    fecha_inicio: str,  # YYYY-MM-DD
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> list[CitaResponse]:
    """Devuelve citas de los 7 días a partir de fecha_inicio, con nombre de paciente."""
    try:
        inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=422, detail="fecha_inicio debe ser YYYY-MM-DD")

    citas = obtener_citas_semana(db, usuario.consultorio_id, inicio)

    resultado = []
    for cita in citas:
        paciente = db.get(Paciente, cita.paciente_id)
        nombre = paciente.nombre if paciente else "—"
        resultado.append(_cita_response(cita, nombre))

    return resultado


# ── POST /api/citas ───────────────────────────────────────────────────────────

@router.post("/api/citas", response_model=CitaResponse, status_code=201)
def crear(
    data: CitaCreate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> CitaResponse:
    """Crea una nueva cita tras validar paciente y disponibilidad horaria."""
    # Verificar que el paciente exista y pertenezca al consultorio
    paciente = db.get(Paciente, data.paciente_id)
    if not paciente or paciente.consultorio_id != usuario.consultorio_id:
        raise HTTPException(status_code=404, detail="Paciente no encontrado en este consultorio")

    # Validar que no haya choque horario
    if not validar_disponibilidad(
        db,
        usuario.consultorio_id,
        usuario.id,
        data.fecha_hora,
        data.duracion_min,
    ):
        raise HTTPException(status_code=409, detail="El horario solapa con otra cita")

    cita = crear_cita(db, data, usuario)
    return _cita_response(cita, paciente.nombre)


# ── PATCH /api/citas/{id} ─────────────────────────────────────────────────────

@router.patch("/api/citas/{cita_id}", response_model=CitaResponse)
def actualizar(
    cita_id: int,
    data: CitaUpdate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> CitaResponse:
    """Actualiza campos de una cita existente del consultorio."""
    cita = _get_cita_del_consultorio(cita_id, usuario.consultorio_id, db)

    # Aplicar solo los campos enviados
    if data.fecha_hora is not None:
        # Revalidar disponibilidad si cambia la hora
        if not validar_disponibilidad(
            db,
            usuario.consultorio_id,
            cita.profesional_id,
            data.fecha_hora,
            data.duracion_min or cita.duracion_min,
            excluir_cita_id=cita.id,
        ):
            raise HTTPException(status_code=409, detail="El horario solapa con otra cita")
        cita.fecha_hora = data.fecha_hora

    if data.duracion_min is not None:
        cita.duracion_min = data.duracion_min
    if data.motivo is not None:
        cita.motivo = data.motivo
    if data.estado is not None:
        if data.estado not in _ESTADOS_VALIDOS:
            raise HTTPException(status_code=422, detail=f"Estado inválido: {data.estado}")
        cita.estado = data.estado

    db.add(cita)
    db.commit()
    db.refresh(cita)

    paciente = db.get(Paciente, cita.paciente_id)
    return _cita_response(cita, paciente.nombre if paciente else "—")


# ── PATCH /api/citas/{id}/estado ──────────────────────────────────────────────

@router.patch("/api/citas/{cita_id}/estado", response_model=CitaResponse)
def cambiar_estado(
    cita_id: int,
    data: CitaEstadoUpdate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> CitaResponse:
    """Cambia únicamente el estado de una cita."""
    if data.estado not in _ESTADOS_VALIDOS:
        raise HTTPException(status_code=422, detail=f"Estado inválido: {data.estado}")

    cita = _get_cita_del_consultorio(cita_id, usuario.consultorio_id, db)
    cita.estado = data.estado
    db.add(cita)
    db.commit()
    db.refresh(cita)

    paciente = db.get(Paciente, cita.paciente_id)
    return _cita_response(cita, paciente.nombre if paciente else "—")


# ── DELETE /api/citas/{id} ────────────────────────────────────────────────────

@router.delete("/api/citas/{cita_id}", status_code=204)
def eliminar(
    cita_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> None:
    """Elimina una cita del consultorio."""
    cita = _get_cita_del_consultorio(cita_id, usuario.consultorio_id, db)
    db.delete(cita)
    db.commit()


# ── GET /api/citas/{id}/recordatorio ──────────────────────────────────────────

@router.get("/api/citas/{cita_id}/recordatorio")
def recordatorio_whatsapp(
    cita_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict:
    """Genera el enlace de WhatsApp (wa.me) con el mensaje de recordatorio de cita."""
    from app.models.consultorio import Consultorio
    from app.services.whatsapp import generar_enlace_whatsapp, generar_mensaje_recordatorio

    cita = _get_cita_del_consultorio(cita_id, usuario.consultorio_id, db)
    paciente = db.get(Paciente, cita.paciente_id)
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    if not paciente.telefono or not paciente.telefono.strip():
        raise HTTPException(
            status_code=400,
            detail="El paciente no tiene un número de teléfono registrado",
        )

    consultorio = db.get(Consultorio, usuario.consultorio_id)
    mensaje = generar_mensaje_recordatorio(paciente, cita, consultorio)

    try:
        enlace = generar_enlace_whatsapp(paciente.telefono, mensaje)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"enlace": enlace}
