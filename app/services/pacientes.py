"""Servicio de lógica de negocio para la gestión de pacientes y dueños."""

from datetime import date
from typing import Any, Optional

from sqlmodel import Session, col, desc, or_, select

from app.models.cita import Cita
from app.models.consulta import Consulta
from app.models.dueno import Dueno
from app.models.paciente import Paciente
from app.models.pago import Pago
from app.models.usuario import Usuario
from app.schemas.paciente import DuenoCreate, PacienteCreate, PacienteUpdate


def calcular_edad(fecha_nacimiento: date) -> dict:
    """Calcula la edad exacta a partir de la fecha de nacimiento.

    Determinista: dado el mismo input y fecha actual, produce el mismo output.
    Retorna un dict con 'anios', 'meses', 'dias' y 'texto' legible.
    """
    hoy = date.today()
    if fecha_nacimiento > hoy:
        return {"anios": 0, "meses": 0, "dias": 0, "texto": "Fecha futura"}

    anios = hoy.year - fecha_nacimiento.year
    meses = hoy.month - fecha_nacimiento.month
    dias = hoy.day - fecha_nacimiento.day

    if dias < 0:
        meses -= 1
        # Días del mes anterior
        import calendar
        ultimo_mes = hoy.month - 1 or 12
        ultimo_anio = hoy.year if hoy.month > 1 else hoy.year - 1
        dias += calendar.monthrange(ultimo_anio, ultimo_mes)[1]

    if meses < 0:
        anios -= 1
        meses += 12

    if anios > 0:
        texto = f"{anios} año{'s' if anios != 1 else ''}"
        if meses > 0:
            texto += f" y {meses} mes{'es' if meses != 1 else ''}"
    elif meses > 0:
        texto = f"{meses} mes{'es' if meses != 1 else ''}"
        if dias > 0:
            texto += f" y {dias} día{'s' if dias != 1 else ''}"
    else:
        texto = f"{dias} día{'s' if dias != 1 else ''}"

    return {"anios": anios, "meses": meses, "dias": dias, "texto": texto}


def buscar_pacientes(
    db: Session,
    consultorio_id: int,
    q: str = "",
    tipo: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Busca y lista pacientes de un consultorio con filtro opcional por texto y tipo.

    Calcula la última visita a partir de la fecha de su última cita completada o consulta.
    """
    stmt = select(Paciente).where(
        Paciente.consultorio_id == consultorio_id,
        Paciente.demo == False,  # Usado también para soft delete si demo=True
    )

    if tipo and tipo.upper() in ("HUMANO", "MASCOTA"):
        stmt = stmt.where(Paciente.tipo == tipo.upper())

    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Paciente.nombre.ilike(term),
                Paciente.cedula.ilike(term),
                Paciente.telefono.ilike(term),
            )
        )

    pacientes = db.exec(stmt.order_by(Paciente.nombre)).all()
    resultado = []

    for p in pacientes:
        # Obtener última visita
        ultima_cita = db.exec(
            select(Cita)
            .where(
                Cita.consultorio_id == consultorio_id,
                Cita.paciente_id == p.id,
                Cita.estado.in_(["completada", "confirmada"]),
            )
            .order_by(desc(Cita.fecha_hora))
        ).first()

        ultima_consulta = db.exec(
            select(Consulta)
            .where(
                Consulta.consultorio_id == consultorio_id,
                Consulta.paciente_id == p.id,
            )
            .order_by(desc(Consulta.fecha))
        ).first()

        fechas = []
        if ultima_cita:
            fechas.append(ultima_cita.fecha_hora)
        if ultima_consulta:
            fechas.append(ultima_consulta.fecha)

        ultima_visita = max(fechas) if fechas else None

        resultado.append({
            "id": p.id,
            "nombre": p.nombre,
            "telefono": p.telefono,
            "email": p.email,
            "cedula": p.cedula,
            "tipo": p.tipo,
            "fecha_nacimiento": p.fecha_nacimiento,
            "alergias": p.alergias,
            "notas_generales": p.notas_generales,
            "especie": p.especie,
            "raza": p.raza,
            "peso_kg": p.peso_kg,
            "microchip": p.microchip,
            "dueno_id": p.dueno_id,
            "creado_en": p.creado_en,
            "ultima_visita": ultima_visita,
        })

    return resultado


def obtener_paciente_detalle(
    db: Session,
    paciente_id: int,
    consultorio_id: int,
    usuario: Optional[Usuario] = None,
) -> Optional[dict[str, Any]]:
    """Obtiene la información detallada del paciente, su dueño (si aplica) y su historial clínico."""
    paciente = db.exec(
        select(Paciente).where(
            Paciente.id == paciente_id,
            Paciente.consultorio_id == consultorio_id,
        )
    ).first()

    if not paciente:
        return None

    # Dueño si es mascota
    dueno = None
    if paciente.dueno_id:
        dueno = db.exec(
            select(Dueno).where(
                Dueno.id == paciente.dueno_id,
                Dueno.consultorio_id == consultorio_id,
            )
        ).first()

    # Historial de citas
    citas = db.exec(
        select(Cita)
        .where(
            Cita.consultorio_id == consultorio_id,
            Cita.paciente_id == paciente_id,
        )
        .order_by(desc(Cita.fecha_hora))
    ).all()

    # Historial de consultas
    consultas = db.exec(
        select(Consulta)
        .where(
            Consulta.consultorio_id == consultorio_id,
            Consulta.paciente_id == paciente_id,
        )
        .order_by(desc(Consulta.fecha))
    ).all()

    # Historial de pagos
    pagos = db.exec(
        select(Pago)
        .where(
            Pago.consultorio_id == consultorio_id,
            Pago.paciente_id == paciente_id,
        )
        .order_by(desc(Pago.fecha))
    ).all()

    citas_data = [
        {
            "id": c.id,
            "fecha_hora": c.fecha_hora,
            "duracion_min": c.duracion_min,
            "motivo": c.motivo,
            "estado": c.estado,
        }
        for c in citas
    ]

    es_asistente = bool(usuario and usuario.rol == "ASISTENTE")
    from app.services.cifrado import descifrar

    consultas_data = [
        {
            "id": con.id,
            "fecha": con.fecha,
            "motivo": con.motivo,
            "diagnostico": None if es_asistente else descifrar(con.diagnostico),
            "nota": None if es_asistente else descifrar(con.nota),
            "indicaciones": None if es_asistente else descifrar(con.indicaciones),
            "proxima_cita": con.proxima_cita,
        }
        for con in consultas
    ]

    pagos_data = [
        {
            "id": pg.id,
            "monto": pg.monto,
            "moneda": pg.moneda,
            "metodo": pg.metodo,
            "estado": pg.estado,
            "fecha": pg.fecha,
        }
        for pg in pagos
    ]

    dueno_data = None
    if dueno:
        dueno_data = {
            "id": dueno.id,
            "consultorio_id": dueno.consultorio_id,
            "nombre": dueno.nombre,
            "cedula": dueno.cedula,
            "telefono": dueno.telefono,
            "email": dueno.email,
            "direccion": dueno.direccion,
            "creado_en": dueno.creado_en,
        }

    return {
        "paciente": {
            "id": paciente.id,
            "nombre": paciente.nombre,
            "telefono": paciente.telefono,
            "email": paciente.email,
            "cedula": paciente.cedula,
            "tipo": paciente.tipo,
            "fecha_nacimiento": paciente.fecha_nacimiento,
            "alergias": paciente.alergias,
            "notas_generales": paciente.notas_generales,
            "especie": paciente.especie,
            "raza": paciente.raza,
            "peso_kg": paciente.peso_kg,
            "microchip": paciente.microchip,
            "dueno_id": paciente.dueno_id,
            "creado_en": paciente.creado_en,
            "ultima_visita": citas_data[0]["fecha_hora"] if citas_data else None,
        },
        "dueno": dueno_data,
        "historial": {
            "citas": citas_data,
            "consultas": consultas_data,
            "pagos": pagos_data,
        },
    }


def crear_paciente_completo(
    db: Session,
    data: PacienteCreate,
    usuario: Usuario,
) -> Paciente:
    """Crea un nuevo paciente con todos sus atributos."""
    paciente = Paciente(
        consultorio_id=usuario.consultorio_id,
        nombre=data.nombre,
        telefono=data.telefono,
        email=data.email,
        cedula=data.cedula,
        tipo=data.tipo.upper() if data.tipo else "HUMANO",
        fecha_nacimiento=data.fecha_nacimiento,
        alergias=data.alergias,
        notas_generales=data.notas_generales,
        especie=data.especie,
        raza=data.raza,
        peso_kg=data.peso_kg,
        microchip=data.microchip,
        dueno_id=data.dueno_id,
    )
    db.add(paciente)
    db.commit()
    db.refresh(paciente)
    return paciente


def actualizar_paciente(
    db: Session,
    paciente_id: int,
    data: PacienteUpdate,
    consultorio_id: int,
) -> Optional[Paciente]:
    """Actualiza los campos proporcionados de un paciente existente."""
    paciente = db.exec(
        select(Paciente).where(
            Paciente.id == paciente_id,
            Paciente.consultorio_id == consultorio_id,
        )
    ).first()

    if not paciente:
        return None

    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        if key == "tipo" and value:
            setattr(paciente, key, value.upper())
        else:
            setattr(paciente, key, value)

    db.add(paciente)
    db.commit()
    db.refresh(paciente)
    return paciente


def eliminar_paciente(
    db: Session,
    paciente_id: int,
    consultorio_id: int,
) -> bool:
    """Elimina un paciente: borrado físico si no tiene historial, o soft delete (demo=True) si tiene historial."""
    paciente = db.exec(
        select(Paciente).where(
            Paciente.id == paciente_id,
            Paciente.consultorio_id == consultorio_id,
        )
    ).first()

    if not paciente:
        return False

    # Verificar si tiene historial en citas, consultas o pagos
    tiene_citas = db.exec(select(Cita).where(Cita.paciente_id == paciente_id)).first() is not None
    tiene_consultas = db.exec(select(Consulta).where(Consulta.paciente_id == paciente_id)).first() is not None
    tiene_pagos = db.exec(select(Pago).where(Pago.paciente_id == paciente_id)).first() is not None

    tiene_historial = tiene_citas or tiene_consultas or tiene_pagos

    if tiene_historial:
        # Soft delete marcando demo=True (inactivo/oculto)
        paciente.demo = True
        db.add(paciente)
        db.commit()
    else:
        # Borrado físico
        db.delete(paciente)
        db.commit()

    return True


def crear_dueno(
    db: Session,
    data: DuenoCreate,
    consultorio_id: int,
) -> Dueno:
    """Crea un nuevo dueño en el consultorio."""
    dueno = Dueno(
        consultorio_id=consultorio_id,
        nombre=data.nombre,
        cedula=data.cedula,
        telefono=data.telefono,
        email=data.email,
        direccion=data.direccion,
    )
    db.add(dueno)
    db.commit()
    db.refresh(dueno)
    return dueno


def buscar_duenos(
    db: Session,
    consultorio_id: int,
    q: str = "",
) -> list[Dueno]:
    """Lista dueños con filtro de búsqueda opcional por nombre, cédula o teléfono."""
    stmt = select(Dueno).where(Dueno.consultorio_id == consultorio_id)
    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Dueno.nombre.ilike(term),
                Dueno.cedula.ilike(term),
                Dueno.telefono.ilike(term),
            )
        )
    return list(db.exec(stmt.order_by(Dueno.nombre)).all())
