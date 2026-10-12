"""Servicios de lógica de negocio para la agenda de citas."""

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models.cita import Cita
from app.models.usuario import Usuario
from app.schemas.cita import CitaCreate


def obtener_citas_semana(
    db: Session,
    consultorio_id: int,
    fecha_inicio: datetime,
) -> list[Cita]:
    """Devuelve las citas del consultorio en los 7 días desde fecha_inicio.

    Args:
        db: Sesión de base de datos.
        consultorio_id: ID del consultorio a filtrar.
        fecha_inicio: Primer instante del rango (inclusive).

    Returns:
        Lista de citas ordenadas por fecha_hora.
    """
    fecha_fin = fecha_inicio + timedelta(days=7)
    citas = db.exec(
        select(Cita)
        .where(
            Cita.consultorio_id == consultorio_id,
            Cita.fecha_hora >= fecha_inicio,
            Cita.fecha_hora < fecha_fin,
        )
        .order_by(Cita.fecha_hora)
    ).all()
    return list(citas)


def validar_disponibilidad(
    db: Session,
    consultorio_id: int,
    profesional_id: int,
    fecha_hora: datetime,
    duracion_min: int,
    excluir_cita_id: int | None = None,
) -> bool:
    """Verifica que el profesional no tenga otra cita que solape el horario.

    Dos citas chocan si una comienza antes de que termine la otra.

    Args:
        db: Sesión de base de datos.
        consultorio_id: ID del consultorio.
        profesional_id: ID del profesional a verificar.
        fecha_hora: Inicio de la nueva cita.
        duracion_min: Duración en minutos de la nueva cita.
        excluir_cita_id: ID de cita a ignorar (útil al editar).

    Returns:
        True si el horario está disponible, False si hay choque.
    """
    fin_nueva = fecha_hora + timedelta(minutes=duracion_min)

    # Citas activas del profesional en el rango
    stmt = select(Cita).where(
        Cita.consultorio_id == consultorio_id,
        Cita.profesional_id == profesional_id,
        Cita.estado.in_(["pendiente", "confirmada"]),
        # La cita existente comienza antes de que termine la nueva
        Cita.fecha_hora < fin_nueva,
    )
    if excluir_cita_id:
        stmt = stmt.where(Cita.id != excluir_cita_id)

    existentes = db.exec(stmt).all()

    for cita in existentes:
        fin_existente = cita.fecha_hora + timedelta(minutes=cita.duracion_min)
        # Hay choque si la nueva comienza antes de que termine la existente
        if fecha_hora < fin_existente:
            return False

    return True


def crear_cita(db: Session, data: CitaCreate, usuario: Usuario) -> Cita:
    """Crea y persiste una nueva cita en la base de datos.

    Args:
        db: Sesión de base de datos.
        data: Datos validados de la cita.
        usuario: Usuario que crea la cita (médico o asistente).

    Returns:
        La cita recién creada y refrescada.
    """
    cita = Cita(
        consultorio_id=usuario.consultorio_id,
        paciente_id=data.paciente_id,
        profesional_id=usuario.id,
        fecha_hora=data.fecha_hora,
        duracion_min=data.duracion_min,
        motivo=data.motivo,
        creada_por=usuario.id,
    )
    db.add(cita)
    db.commit()
    db.refresh(cita)
    return cita
