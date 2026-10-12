import json
"""Servicios de lógica de negocio para la Agenda Pública (sin autenticación)."""

from datetime import date, datetime, time, timedelta, timezone
import re
import unicodedata
from typing import Any, Dict, List, Optional

from sqlmodel import Session, col, select

from app.models.cita import Cita
from app.models.configuracion import Configuracion
from app.models.consultorio import Consultorio
from app.models.paciente import Paciente
from app.models.usuario import Usuario
from app.services.agenda import validar_disponibilidad
from app.services.whatsapp import generar_enlace_whatsapp

# Rate limiting en memoria: { ip: [timestamp_float, ...] }
_RATE_LIMIT_REGISTRO: Dict[str, List[float]] = {}
_MAX_PETICIONES_HORA = 5
_VENTANA_SEGUNDOS = 3600


def limpiar_rate_limit() -> None:
    """Utilidad para limpiar el registro de rate limits (útil en tests)."""
    _RATE_LIMIT_REGISTRO.clear()


def verificar_rate_limit(ip: Optional[str]) -> bool:
    """Verifica si la IP ha excedido el límite de reservas/solicitudes por hora.

    Permite hasta 5 peticiones por hora por IP.
    """
    if not ip:
        return True

    ahora = datetime.now(timezone.utc).timestamp()
    historial = _RATE_LIMIT_REGISTRO.get(ip, [])
    # Filtrar sólo los eventos dentro de la ventana de 1 hora
    recientes = [t for t in historial if ahora - t < _VENTANA_SEGUNDOS]
    if len(recientes) >= _MAX_PETICIONES_HORA:
        _RATE_LIMIT_REGISTRO[ip] = recientes
        return False

    recientes.append(ahora)
    _RATE_LIMIT_REGISTRO[ip] = recientes
    return True


def slugify(texto: str) -> str:
    """Convierte un texto en un slug URL-safe sin acentos ni caracteres especiales."""
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^\w\s-]", "", texto).strip().lower()
    slug = re.sub(r"[-\s]+", "-", texto)
    return slug or "consultorio"


def generar_slug_unico(db: Session, nombre: str, consultorio_id: Optional[int] = None) -> str:
    """Genera un slug único para el consultorio a partir de su nombre."""
    base_slug = slugify(nombre)
    slug_candidato = base_slug
    contador = 1

    while True:
        query = select(Consultorio).where(Consultorio.slug == slug_candidato)
        if consultorio_id is not None:
            query = query.where(Consultorio.id != consultorio_id)
        existente = db.exec(query).first()
        if not existente:
            return slug_candidato
        contador += 1
        slug_candidato = f"{base_slug}-{contador}"


def _parse_hora_str(hora_str: str) -> time:
    """Parsea una cadena 'HH:MM' a un objeto datetime.time."""
    partes = hora_str.strip().split(":")
    return time(int(partes[0]), int(partes[1]))


def _nombre_dia_semana(fecha: date) -> str:
    """Devuelve código de día de la semana (LUN, MAR, MIE, JUE, VIE, SAB, DOM)."""
    dias = ["LUN", "MAR", "MIE", "JUE", "VIE", "SAB", "DOM"]
    return dias[fecha.weekday()]


def parsear_horario_publico(consultorio, db: Optional[Session] = None) -> dict:
    """Devuelve el horario en dict. Si no existe, usa fallback."""
    if consultorio and getattr(consultorio, "horario_publico", None):
        try:
            raw = consultorio.horario_publico
            data = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(data, dict):
                return {
                    "dias": data.get("dias", [1, 2, 3, 4, 5]),
                    "hora_apertura": data.get("hora_apertura", "08:00"),
                    "hora_cierre": data.get("hora_cierre", "17:00"),
                    "pausa_inicio": data.get("pausa_inicio"),
                    "pausa_fin": data.get("pausa_fin"),
                    "limite_diario": int(data.get("limite_diario", 0) or 0),
                    "dias_bloqueados": data.get("dias_bloqueados", []),
            }
        except Exception:
            pass

    cfg = None
    if db is not None and consultorio is not None and getattr(consultorio, "id", None):
        cfg = db.exec(select(Configuracion).where(Configuracion.consultorio_id == consultorio.id)).first()

    dias_map = {"DOM": 0, "LUN": 1, "MAR": 2, "MIE": 3, "JUE": 4, "VIE": 5, "SAB": 6}
    dias_lista = [1, 2, 3, 4, 5]
    if cfg and cfg.dias_laborables:
        cods = [d.strip().upper() for d in cfg.dias_laborables.split(",") if d.strip()]
        mapeados = [dias_map[c] for c in cods if c in dias_map]
        if mapeados:
            dias_lista = mapeados

    return {
        "dias": dias_lista if dias_lista else [1, 2, 3, 4, 5],
        "hora_apertura": cfg.horario_apertura if (cfg and cfg.horario_apertura) else "08:00",
        "hora_cierre": cfg.horario_cierre if (cfg and cfg.horario_cierre) else "18:00",
        "pausa_inicio": None,
        "pausa_fin": None,
        "limite_diario": 0,
        "dias_bloqueados": [],
    }


def obtener_slots_disponibles(db: Session, consultorio_id: int, dias: int = 7) -> Dict[str, List[str]]:
    """Calcula y devuelve los slots disponibles para los próximos `dias` días."""
    consultorio = db.get(Consultorio, consultorio_id)
    if not consultorio or not consultorio.agenda_publica_activa:
        return {}

    horario = parsear_horario_publico(consultorio, db=db)
    dias_permitidos = set(horario.get("dias", [1, 2, 3, 4, 5]))
    hora_apertura_str = horario.get("hora_apertura", "08:00")
    hora_cierre_str = horario.get("hora_cierre", "17:00")
    pausa_inicio_str = horario.get("pausa_inicio")
    pausa_fin_str = horario.get("pausa_fin")
    limite_diario = int(horario.get("limite_diario", 0) or 0)
    dias_bloqueados = set(horario.get("dias_bloqueados", []))

    duracion = consultorio.duracion_cita_publica or 30

    medico = db.exec(
        select(Usuario).where(
            Usuario.consultorio_id == consultorio_id,
            Usuario.rol == "MEDICO",
            Usuario.activo == True,
        )
    ).first()
    profesional_id = medico.id if medico else 1

    apertura_t = _parse_hora_str(hora_apertura_str)
    cierre_t = _parse_hora_str(hora_cierre_str)

    pausa_ini_t = _parse_hora_str(pausa_inicio_str) if pausa_inicio_str else None
    pausa_fin_t = _parse_hora_str(pausa_fin_str) if pausa_fin_str else None

    ahora = datetime.now(timezone.utc)
    hoy = ahora.date()

    slots_por_dia: Dict[str, List[str]] = {}

    for i in range(dias):
        fecha_eval = hoy + timedelta(days=i)
        fecha_key = fecha_eval.isoformat()

        if fecha_key in dias_bloqueados:
            continue

        dia_semana_num = (fecha_eval.weekday() + 1) % 7
        if dia_semana_num not in dias_permitidos:
            continue

        if limite_diario > 0:
            inicio_dia = datetime.combine(fecha_eval, time.min, tzinfo=timezone.utc)
            fin_dia = datetime.combine(fecha_eval, time.max, tzinfo=timezone.utc)
            citas_dia = db.exec(
                select(Cita).where(
                    Cita.consultorio_id == consultorio_id,
                    Cita.fecha_hora >= inicio_dia,
                    Cita.fecha_hora <= fin_dia,
                    Cita.estado.notin_(["CANCELADA"]),
                )
            ).all()
            if len(citas_dia) >= limite_diario:
                slots_por_dia[fecha_key] = []
                continue

        slots_dia: List[str] = []

        actual_dt = datetime.combine(fecha_eval, apertura_t, tzinfo=timezone.utc)
        limite_dt = datetime.combine(fecha_eval, cierre_t, tzinfo=timezone.utc)

        while actual_dt + timedelta(minutes=duracion) <= limite_dt:
            slot_fin_dt = actual_dt + timedelta(minutes=duracion)

            if actual_dt <= ahora:
                actual_dt += timedelta(minutes=duracion)
                continue

            if pausa_ini_t and pausa_fin_t:
                pausa_ini_dt = datetime.combine(fecha_eval, pausa_ini_t, tzinfo=timezone.utc)
                pausa_fin_dt = datetime.combine(fecha_eval, pausa_fin_t, tzinfo=timezone.utc)
                if actual_dt < pausa_fin_dt and slot_fin_dt > pausa_ini_dt:
                    actual_dt += timedelta(minutes=duracion)
                    continue

            disponible = validar_disponibilidad(
                db=db,
                consultorio_id=consultorio_id,
                profesional_id=profesional_id,
                fecha_hora=actual_dt,
                duracion_min=duracion,
            )

            if disponible:
                slots_dia.append(actual_dt.strftime("%H:%M"))

            actual_dt += timedelta(minutes=duracion)

        slots_por_dia[fecha_key] = slots_dia

    return slots_por_dia



def reservar_cita_publica(
    db: Session,
    slug: str,
    datos: Dict[str, Any],
    ip: Optional[str] = None,
) -> Dict[str, Any]:
    """Reserva una cita desde el portal público."""
    if not verificar_rate_limit(ip):
        raise ValueError("Límite de solicitudes excedido. Intente de nuevo más tarde.")

    consultorio = db.exec(select(Consultorio).where(Consultorio.slug == slug)).first()
    if not consultorio:
        raise ValueError("El consultorio no existe.")
    if not consultorio.agenda_publica_activa:
        raise ValueError("La agenda pública no está habilitada para este consultorio.")

    nombre = str(datos.get("nombre", "")).strip()
    telefono = str(datos.get("telefono", "")).strip()
    motivo = str(datos.get("motivo", "")).strip()
    fecha_str = str(datos.get("fecha", "")).strip()
    hora_str = str(datos.get("hora", "")).strip()

    # Validaciones obligatorias
    if len(nombre) < 2 or len(nombre) > 100:
        raise ValueError("El nombre debe tener entre 2 y 100 caracteres.")
    solo_digitos = re.sub(r"[^\d]", "", telefono)
    if len(solo_digitos) < 7 or len(solo_digitos) > 15:
        raise ValueError("El teléfono debe contener entre 7 y 15 dígitos.")
    if len(motivo) < 3 or len(motivo) > 500:
        raise ValueError("El motivo debe tener entre 3 y 500 caracteres.")

    try:
        fecha_obj = date.fromisoformat(fecha_str)
        hora_obj = _parse_hora_str(hora_str)
        fecha_hora_cita = datetime.combine(fecha_obj, hora_obj, tzinfo=timezone.utc)
    except Exception:
        raise ValueError("Fecha u hora con formato inválido.")

    if fecha_hora_cita <= datetime.now(timezone.utc):
        raise ValueError("No se puede agendar una cita en el pasado.")

    duracion = consultorio.duracion_cita_publica or 30

    # Buscar médico titular
    medico = db.exec(
        select(Usuario).where(
            Usuario.consultorio_id == consultorio.id,
            Usuario.rol == "MEDICO",
            Usuario.activo == True,
        )
    ).first()
    profesional_id = medico.id if medico else 1

    # Verificar disponibilidad en tiempo real
    if not validar_disponibilidad(
        db=db,
        consultorio_id=consultorio.id,
        profesional_id=profesional_id,
        fecha_hora=fecha_hora_cita,
        duracion_min=duracion,
    ):
        raise ValueError("El horario seleccionado ya no se encuentra disponible. Por favor elija otro.")

    # Buscar o crear Paciente con este teléfono
    paciente = db.exec(
        select(Paciente).where(
            Paciente.consultorio_id == consultorio.id,
            Paciente.telefono == telefono,
        )
    ).first()

    if not paciente:
        paciente = Paciente(
            consultorio_id=consultorio.id,
            tipo="HUMANO" if consultorio.tipo != "VETERINARIO" else "MASCOTA",
            nombre=nombre,
            telefono=telefono,
            notas_generales="Registrado vía Agenda Pública",
            demo=False,
        )
        db.add(paciente)
        db.commit()
        db.refresh(paciente)

    # Crear la cita
    cita = Cita(
        consultorio_id=consultorio.id,
        paciente_id=paciente.id,
        profesional_id=profesional_id,
        fecha_hora=fecha_hora_cita,
        duracion_min=duracion,
        estado="confirmada",
        motivo=motivo,
        creada_por=profesional_id,
        origen="publico",
        nombre_solicitante=nombre,
        telefono_solicitante=telefono,
        demo=False,
    )
    db.add(cita)
    db.commit()
    db.refresh(cita)

    # Construir mensaje y enlace de WhatsApp
    tel_destino = consultorio.telefono_whatsapp_publico or consultorio.telefono
    mensaje_whatsapp = (
        f"Hola, soy {nombre}.\n"
        f"Acabo de agendar una cita para el {fecha_str} a las {hora_str}.\n"
        f"Motivo: {motivo}"
    )
    enlace_wa = ""
    try:
        enlace_wa = generar_enlace_whatsapp(tel_destino, mensaje_whatsapp)
    except Exception:
        enlace_wa = ""

    return {
        "cita_id": cita.id,
        "enlace_whatsapp": enlace_wa,
        "mensaje": f"Cita confirmada con éxito para el {fecha_str} a las {hora_str}.",
        "fecha": fecha_str,
        "hora": hora_str,
        "consultorio_nombre": consultorio.nombre,
    }


def solicitar_horario_libre(
    db: Session,
    slug: str,
    datos: Dict[str, Any],
    ip: Optional[str] = None,
) -> Dict[str, Any]:
    """Crea una solicitud de horario libre como fallback cuando el paciente no halla horario."""
    if not verificar_rate_limit(ip):
        raise ValueError("Límite de solicitudes excedido. Intente de nuevo más tarde.")

    consultorio = db.exec(select(Consultorio).where(Consultorio.slug == slug)).first()
    if not consultorio:
        raise ValueError("El consultorio no existe.")
    if not consultorio.agenda_publica_activa:
        raise ValueError("La agenda pública no está habilitada para este consultorio.")

    nombre = str(datos.get("nombre", "")).strip()
    telefono = str(datos.get("telefono", "")).strip()
    motivo = str(datos.get("motivo", "")).strip()
    fecha_pref = str(datos.get("fecha_preferida", "")).strip()
    hora_pref = str(datos.get("hora_preferida", "")).strip()

    if len(nombre) < 2 or len(nombre) > 100:
        raise ValueError("El nombre debe tener entre 2 y 100 caracteres.")
    solo_digitos = re.sub(r"[^\d]", "", telefono)
    if len(solo_digitos) < 7 or len(solo_digitos) > 15:
        raise ValueError("El teléfono debe contener entre 7 y 15 dígitos.")
    if len(motivo) < 3 or len(motivo) > 500:
        raise ValueError("El motivo debe tener entre 3 y 500 caracteres.")

    # Buscar médico titular
    medico = db.exec(
        select(Usuario).where(
            Usuario.consultorio_id == consultorio.id,
            Usuario.rol == "MEDICO",
            Usuario.activo == True,
        )
    ).first()
    profesional_id = medico.id if medico else 1

    motivo_completo = motivo
    if fecha_pref or hora_pref:
        motivo_completo += f" (Preferencia: {fecha_pref or 'Cualquier fecha'} {hora_pref or ''})"

    ahora = datetime.now(timezone.utc)

    # Crear cita tipo solicitud sin slot reservado forzado
    solicitud = Cita(
        consultorio_id=consultorio.id,
        paciente_id=None,
        profesional_id=profesional_id,
        fecha_hora=ahora,
        duracion_min=consultorio.duracion_cita_publica or 30,
        estado="pendiente",
        motivo=motivo_completo,
        creada_por=profesional_id,
        origen="solicitud",
        nombre_solicitante=nombre,
        telefono_solicitante=telefono,
        demo=False,
    )
    db.add(solicitud)
    db.commit()
    db.refresh(solicitud)

    return {
        "solicitud_id": solicitud.id,
        "mensaje": "Su solicitud ha sido enviada con éxito. El equipo se pondrá en contacto pronto.",
    }
