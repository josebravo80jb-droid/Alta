import json
import re
"""Rutas privadas para configuración de consultorio y gestión de solicitudes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from typing import List
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models.cita import Cita
from app.models.consultorio import Consultorio
from app.models.paciente import Paciente
from app.models.usuario import Usuario
from app.services.agenda_publica import generar_slug_unico, slugify, parsear_horario_publico

router = APIRouter(prefix="/api/consultorio", tags=["consultorio"])


class AgendaPublicaConfigUpdate(BaseModel):
    activa: Optional[bool] = None
    slug: Optional[str] = None
    duracion_cita_publica: Optional[int] = Field(None, ge=10, le=120)
    telefono_whatsapp_publico: Optional[str] = None
    bio_publica: Optional[str] = None


@router.get("/agenda-publica")
def get_config_agenda_publica(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Devuelve la configuración actual de agenda pública del consultorio."""
    consultorio = db.get(Consultorio, usuario.consultorio_id)
    if not consultorio:
        raise HTTPException(status_code=404, detail="Consultorio no encontrado")

    # Si no tiene slug asignado, sugerir uno
    slug_sugerido = consultorio.slug or generar_slug_unico(db, consultorio.nombre, consultorio.id)

    return {
        "activa": consultorio.agenda_publica_activa,
        "slug": consultorio.slug or slug_sugerido,
        "duracion_cita_publica": consultorio.duracion_cita_publica or 30,
        "telefono_whatsapp_publico": consultorio.telefono_whatsapp_publico or consultorio.telefono,
        "bio_publica": consultorio.bio_publica or "",
    }


@router.patch("/agenda-publica")
def patch_config_agenda_publica(
    body: AgendaPublicaConfigUpdate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Actualiza la configuración de agenda pública del consultorio (solo médico)."""
    if usuario.rol != "MEDICO":
        raise HTTPException(status_code=403, detail="Solo el médico puede modificar la configuración")

    consultorio = db.get(Consultorio, usuario.consultorio_id)
    if not consultorio:
        raise HTTPException(status_code=404, detail="Consultorio no encontrado")

    if body.slug is not None:
        nuevo_slug = slugify(body.slug)
        # Validar que sea único o pertenezca a este consultorio
        otro = db.exec(
            select(Consultorio).where(
                Consultorio.slug == nuevo_slug,
                Consultorio.id != consultorio.id,
            )
        ).first()
        if otro:
            raise HTTPException(status_code=400, detail="El enlace (slug) ya está en uso por otro consultorio.")
        consultorio.slug = nuevo_slug

    if body.activa is not None:
        consultorio.agenda_publica_activa = body.activa
        # Si activa y no tenía slug, generar uno
        if consultorio.agenda_publica_activa and not consultorio.slug:
            consultorio.slug = generar_slug_unico(db, consultorio.nombre, consultorio.id)

    if body.duracion_cita_publica is not None:
        consultorio.duracion_cita_publica = body.duracion_cita_publica

    if body.telefono_whatsapp_publico is not None:
        consultorio.telefono_whatsapp_publico = body.telefono_whatsapp_publico.strip()

    if body.bio_publica is not None:
        consultorio.bio_publica = body.bio_publica.strip()

    db.add(consultorio)
    db.commit()
    db.refresh(consultorio)

    return {
        "ok": True,
        "mensaje": "Configuración de agenda pública actualizada",
        "activa": consultorio.agenda_publica_activa,
        "slug": consultorio.slug,
        "duracion_cita_publica": consultorio.duracion_cita_publica,
        "telefono_whatsapp_publico": consultorio.telefono_whatsapp_publico,
        "bio_publica": consultorio.bio_publica,
    }


@router.get("/solicitudes")
def listar_solicitudes(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Lista las solicitudes de horario libre pendientes."""
    solicitudes = db.exec(
        select(Cita)
        .where(
            Cita.consultorio_id == usuario.consultorio_id,
            Cita.origen == "solicitud",
            Cita.estado == "pendiente",
        )
        .order_by(Cita.creado_en.desc())
    ).all()

    return [
        {
            "id": s.id,
            "nombre": s.nombre_solicitante or "Sin nombre",
            "telefono": s.telefono_solicitante or "Sin teléfono",
            "motivo": s.motivo,
            "fecha_creacion": s.creado_en.isoformat(),
        }
        for s in solicitudes
    ]


@router.post("/solicitudes/{id}/confirmar")
def confirmar_solicitud(
    id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Convierte una solicitud pendiente en cita confirmada creando el paciente si no existe."""
    if usuario.rol != "MEDICO":
        raise HTTPException(status_code=403, detail="Solo el médico puede confirmar solicitudes")

    solicitud = db.get(Cita, id)
    if not solicitud or solicitud.consultorio_id != usuario.consultorio_id:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    # Buscar o crear paciente
    consultorio = db.get(Consultorio, usuario.consultorio_id)
    paciente = None
    if solicitud.telefono_solicitante:
        paciente = db.exec(
            select(Paciente).where(
                Paciente.consultorio_id == consultorio.id,
                Paciente.telefono == solicitud.telefono_solicitante,
            )
        ).first()

    if not paciente:
        paciente = Paciente(
            consultorio_id=consultorio.id,
            tipo="HUMANO" if consultorio.tipo != "VETERINARIO" else "MASCOTA",
            nombre=solicitud.nombre_solicitante or "Paciente de Solicitud",
            telefono=solicitud.telefono_solicitante,
            notas_generales="Creado al confirmar solicitud pública de horario",
            demo=False,
        )
        db.add(paciente)
        db.commit()
        db.refresh(paciente)

    solicitud.paciente_id = paciente.id
    solicitud.estado = "confirmada"
    solicitud.origen = "publico"
    db.add(solicitud)
    db.commit()

    return {"ok": True, "mensaje": "Solicitud confirmada exitosamente."}


@router.post("/solicitudes/{id}/rechazar")
def rechazar_solicitud(
    id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Marca la solicitud como cancelada."""
    if usuario.rol != "MEDICO":
        raise HTTPException(status_code=403, detail="Solo el médico puede rechazar solicitudes")

    solicitud = db.get(Cita, id)
    if not solicitud or solicitud.consultorio_id != usuario.consultorio_id:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    solicitud.estado = "cancelada"
    db.add(solicitud)
    db.commit()

    return {"ok": True, "mensaje": "Solicitud rechazada."}


class HorarioPublicoUpdate(BaseModel):
    dias: List[int]
    hora_apertura: str
    hora_cierre: str
    pausa_inicio: Optional[str] = None
    pausa_fin: Optional[str] = None
    limite_diario: int = 0
    dias_bloqueados: List[str] = Field(default_factory=list)

    @field_validator("hora_apertura", "hora_cierre")
    @classmethod
    def validar_hora_obligatoria(cls, v: str) -> str:
        if not re.match(r"^([01][0-9]|2[0-3]):[0-5][0-9]$", v.strip()):
            raise ValueError("Formato de hora inválido (debe ser HH:MM)")
        return v.strip()

    @field_validator("pausa_inicio", "pausa_fin")
    @classmethod
    def validar_hora_opcional(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        if not re.match(r"^([01][0-9]|2[0-3]):[0-5][0-9]$", v.strip()):
            raise ValueError("Formato de hora de pausa inválido (debe ser HH:MM)")
        return v.strip()

    @field_validator("dias")
    @classmethod
    def validar_dias(cls, v: List[int]) -> List[int]:
        for d in v:
            if not (0 <= d <= 6):
                raise ValueError("Los días deben estar entre 0 (Dom) y 6 (Sáb)")
        return v

    @field_validator("dias_bloqueados")
    @classmethod
    def validar_dias_bloqueados(cls, v: List[str]) -> List[str]:
        for fecha_str in v:
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", fecha_str.strip()):
                raise ValueError("Formato de fecha bloqueada inválido (debe ser YYYY-MM-DD)")
        return v


@router.get("/horario-publico")
def get_horario_publico(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Devuelve el JSON de horario público actual del consultorio (con fallback)."""
    consultorio = db.get(Consultorio, usuario.consultorio_id)
    if not consultorio:
        raise HTTPException(status_code=404, detail="Consultorio no encontrado")
    return parsear_horario_publico(consultorio, db=db)


@router.patch("/horario-publico")
def patch_horario_publico(
    body: HorarioPublicoUpdate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Actualiza el horario público del consultorio (solo médico)."""
    if usuario.rol != "MEDICO":
        raise HTTPException(status_code=403, detail="Solo el médico puede modificar el horario público")

    consultorio = db.get(Consultorio, usuario.consultorio_id)
    if not consultorio:
        raise HTTPException(status_code=404, detail="Consultorio no encontrado")

    datos_dict = body.model_dump()
    consultorio.horario_publico = json.dumps(datos_dict, ensure_ascii=False)
    db.add(consultorio)
    db.commit()
    db.refresh(consultorio)

    return {
        "ok": True,
        "mensaje": "Horario público actualizado con éxito",
        "horario": datos_dict,
    }
