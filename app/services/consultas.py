"""Servicio de lógica de negocio para consultas clínicas con cifrado simétrico — Módulo 9."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, desc, select

from app.models.consulta import Consulta
from app.models.paciente import Paciente
from app.models.usuario import Usuario
from app.schemas.consulta import ConsultaCreate, ConsultaUpdate
from app.services.cifrado import cifrar, descifrar


def crear_consulta(
    db: Session,
    data: ConsultaCreate,
    usuario: Usuario,
) -> Consulta:
    """Crea una nueva consulta médica cifrando los campos sensibles antes de guardar."""
    paciente = db.exec(
        select(Paciente).where(
            Paciente.id == data.paciente_id,
            Paciente.consultorio_id == usuario.consultorio_id,
        )
    ).first()
    if not paciente:
        raise ValueError("El paciente no existe o no pertenece a este consultorio.")

    # Cifrado transparente de nota, indicaciones y diagnostico
    nota_cifrada = cifrar(data.nota)
    indicaciones_cifradas = cifrar(data.indicaciones or "")
    diagnostico_cifrado = cifrar(data.diagnostico) if data.diagnostico else None

    consulta = Consulta(
        consultorio_id=usuario.consultorio_id,
        paciente_id=data.paciente_id,
        profesional_id=usuario.id,
        cita_id=data.cita_id,
        fecha=datetime.now(timezone.utc),
        motivo=data.motivo,
        nota=nota_cifrada,
        indicaciones=indicaciones_cifradas,
        diagnostico=diagnostico_cifrado,
        proxima_cita=data.proxima_cita,
    )
    db.add(consulta)
    db.commit()
    db.refresh(consulta)
    return consulta


def obtener_consulta(
    db: Session,
    consulta_id: int,
    consultorio_id: int,
) -> Optional[Consulta]:
    """Obtiene una consulta por ID asegurando pertenencia al consultorio y descifrando sus campos."""
    consulta = db.exec(
        select(Consulta).where(
            Consulta.id == consulta_id,
            Consulta.consultorio_id == consultorio_id,
        )
    ).first()

    if not consulta:
        return None

    # Descifrar en memoria antes de devolver
    consulta.nota = descifrar(consulta.nota)
    consulta.indicaciones = descifrar(consulta.indicaciones)
    consulta.diagnostico = descifrar(consulta.diagnostico) if consulta.diagnostico else None
    return consulta


def listar_consultas_paciente(
    db: Session,
    paciente_id: int,
    consultorio_id: int,
) -> list[Consulta]:
    """Lista consultas de un paciente descifrando los campos clínicos."""
    consultas = list(
        db.exec(
            select(Consulta)
            .where(
                Consulta.paciente_id == paciente_id,
                Consulta.consultorio_id == consultorio_id,
            )
            .order_by(desc(Consulta.fecha))
        ).all()
    )

    for c in consultas:
        c.nota = descifrar(c.nota)
        c.indicaciones = descifrar(c.indicaciones)
        c.diagnostico = descifrar(c.diagnostico) if c.diagnostico else None

    return consultas


def actualizar_consulta(
    db: Session,
    consulta_id: int,
    data: ConsultaUpdate,
    consultorio_id: int,
) -> Optional[Consulta]:
    """Actualiza los campos permitidos cifrando los textos sensibles."""
    consulta = db.exec(
        select(Consulta).where(
            Consulta.id == consulta_id,
            Consulta.consultorio_id == consultorio_id,
        )
    ).first()

    if not consulta:
        return None

    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        if key in ("nota", "indicaciones", "diagnostico") and value is not None:
            setattr(consulta, key, cifrar(value))
        else:
            setattr(consulta, key, value)

    db.add(consulta)
    db.commit()
    db.refresh(consulta)

    # Descifrar antes de devolver la instancia al llamador
    consulta.nota = descifrar(consulta.nota)
    consulta.indicaciones = descifrar(consulta.indicaciones)
    consulta.diagnostico = descifrar(consulta.diagnostico) if consulta.diagnostico else None
    return consulta
