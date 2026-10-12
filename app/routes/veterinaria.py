"""Endpoints de la API para el módulo veterinario AltaPet."""

from datetime import date
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models.paciente import Paciente
from app.models.usuario import Usuario
from app.models.vacuna import Vacuna
from app.services.auditoria import registrar as registrar_auditoria
from app.services.veterinaria.dosis import (
    calcular_dosis,
    calcular_dosis_con_concentracion,
    listar_medicamentos,
)
from app.services.veterinaria.especies import listar_especies, obtener_especie
from app.services.veterinaria.razas import es_raza_valida, listar_razas
from app.services.veterinaria.recordatorios import (
    vacunas_proximas_7_dias,
    vacunas_vencidas,
)
from app.services.veterinaria.vacunas import (
    calcular_calendario,
    proxima_dosis as calcular_proxima_dosis,
    vacunas_pendientes,
)

router = APIRouter(prefix="/api/veterinaria", tags=["veterinaria"])


class VacunaCreate(BaseModel):
    paciente_id: int
    tipo: str
    fecha_aplicacion: date
    proxima_dosis: Optional[date] = None
    lote: Optional[str] = None
    laboratorio: Optional[str] = None
    notas: Optional[str] = None


class VacunaResponse(BaseModel):
    id: int
    paciente_id: int
    consultorio_id: int
    tipo: str
    fecha_aplicacion: date
    proxima_dosis: Optional[date] = None
    lote: Optional[str] = None
    laboratorio: Optional[str] = None
    aplicada_por: int
    notas: Optional[str] = None
    demo: bool = False


class VacunaUpdate(BaseModel):
    tipo: Optional[str] = None
    fecha_aplicacion: Optional[date] = None
    proxima_dosis: Optional[date] = None
    lote: Optional[str] = None
    laboratorio: Optional[str] = None
    notas: Optional[str] = None


class DosisRequest(BaseModel):
    medicamento: str
    peso_kg: float
    concentracion_mg_ml: Optional[float] = None


@router.get("/especies")
def get_especies(usuario: Usuario = Depends(get_current_user)):
    """Lista las especies disponibles."""
    return listar_especies()


@router.get("/razas")
def get_razas(especie: str = Query(...), usuario: Usuario = Depends(get_current_user)):
    """Lista las razas según la especie especificada."""
    return listar_razas(especie)


@router.get("/calendario/{paciente_id}")
def get_calendario_vacunas(
    paciente_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Devuelve el calendario teórico y vacunas aplicadas de una mascota."""
    paciente = db.get(Paciente, paciente_id)
    if not paciente or paciente.consultorio_id != usuario.consultorio_id:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    vacunas_aplicadas = db.exec(
        select(Vacuna)
        .where(
            Vacuna.paciente_id == paciente_id,
            Vacuna.consultorio_id == usuario.consultorio_id,
        )
        .order_by(Vacuna.fecha_aplicacion)
    ).all()

    teorico = []
    if paciente.especie and paciente.fecha_nacimiento:
        teorico = calcular_calendario(paciente.especie, paciente.fecha_nacimiento)

    pendientes = vacunas_pendientes(paciente, vacunas_aplicadas)

    return {
        "paciente": {
            "id": paciente.id,
            "nombre": paciente.nombre,
            "especie": paciente.especie,
            "raza": paciente.raza,
            "fecha_nacimiento": paciente.fecha_nacimiento,
            "peso_kg": paciente.peso_kg,
        },
        "vacunas_aplicadas": vacunas_aplicadas,
        "calendario_teorico": teorico,
        "vacunas_pendientes": pendientes,
    }


@router.get("/vacunas/proximas")
def get_vacunas_proximas(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Lista vacunas programadas en los próximos 7 días."""
    return vacunas_proximas_7_dias(db, usuario.consultorio_id)


@router.get("/vacunas/vencidas")
def get_vacunas_vencidas(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Lista vacunas cuya fecha de dosis programada ha vencido."""
    return vacunas_vencidas(db, usuario.consultorio_id)


@router.post("/vacunas", response_model=VacunaResponse, status_code=status.HTTP_201_CREATED)
def registrar_vacuna(
    datos: VacunaCreate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Registra una nueva vacuna administrada a un paciente mascota."""
    paciente = db.get(Paciente, datos.paciente_id)
    if not paciente or paciente.consultorio_id != usuario.consultorio_id:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    prox = datos.proxima_dosis
    if not prox:
        prox = calcular_proxima_dosis({
            "tipo": datos.tipo,
            "fecha_aplicacion": datos.fecha_aplicacion,
        })

    vacuna = Vacuna(
        paciente_id=datos.paciente_id,
        consultorio_id=usuario.consultorio_id,
        tipo=datos.tipo,
        fecha_aplicacion=datos.fecha_aplicacion,
        proxima_dosis=prox,
        lote=datos.lote,
        laboratorio=datos.laboratorio,
        aplicada_por=usuario.id,
        notas=datos.notas,
    )
    db.add(vacuna)
    db.commit()
    db.refresh(vacuna)

    registrar_auditoria(db, usuario.id, "CREATE", "vacuna", vacuna.id)
    return vacuna


@router.put("/vacunas/{id}", response_model=VacunaResponse)
def actualizar_vacuna(
    id: int,
    datos: VacunaUpdate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Actualiza los datos de una vacuna registrada."""
    vacuna = db.get(Vacuna, id)
    if not vacuna or vacuna.consultorio_id != usuario.consultorio_id:
        raise HTTPException(status_code=404, detail="Vacuna no encontrada")

    for k, v in datos.dict(exclude_unset=True).items():
        setattr(vacuna, k, v)

    db.add(vacuna)
    db.commit()
    db.refresh(vacuna)

    registrar_auditoria(db, usuario.id, "UPDATE", "vacuna", vacuna.id)
    return vacuna


@router.delete("/vacunas/{id}")
def borrar_vacuna(
    id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Elimina un registro de vacuna."""
    vacuna = db.get(Vacuna, id)
    if not vacuna or vacuna.consultorio_id != usuario.consultorio_id:
        raise HTTPException(status_code=404, detail="Vacuna no encontrada")

    db.delete(vacuna)
    db.commit()

    registrar_auditoria(db, usuario.id, "DELETE", "vacuna", id)
    return {"mensaje": "Vacuna eliminada correctamente", "id": id}


@router.get("/medicamentos")
def get_medicamentos(usuario: Usuario = Depends(get_current_user)):
    """Lista los medicamentos disponibles para cálculo de dosis."""
    return listar_medicamentos()


@router.post("/dosis")
def post_calcular_dosis(
    datos: DosisRequest,
    usuario: Usuario = Depends(get_current_user),
):
    """Calcula la dosis sugerida orientativa según peso corporal."""
    try:
        if datos.concentracion_mg_ml and datos.concentracion_mg_ml > 0:
            return calcular_dosis_con_concentracion(
                datos.medicamento,
                datos.peso_kg,
                datos.concentracion_mg_ml,
            )
        return calcular_dosis(datos.medicamento, datos.peso_kg)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
