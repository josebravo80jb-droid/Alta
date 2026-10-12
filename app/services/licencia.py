"""Servicio de licencias local para Alta.

100% Python puro. Sin red. Sin IA. Determinista. Coste $0/mes.

Estados válidos:
    trial    — prueba de 30 días desde instalación
    activa   — clave activada dentro de vigencia mensual
    gracia   — vencida hace ≤7 días (solo lectura ampliada)
    expirada — vencida hace >7 días
    bloqueada — hardware_id no coincide (anticopia)
    founder  — acceso permanente, sin licencia requerida
"""

import re
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session, select

from app.config import es_founder as _es_founder_config
from app.models.licencia import LicenciaLocal
from app.services.hardware import obtener_hardware_id

# ── Constantes ───────────────────────────────────────────────────────────────
TRIAL_DIAS: int = 30
GRACIA_DIAS: int = 7
_CLAVE_PATRON = re.compile(r"^ALTA-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$")


# ── Utilidades de fecha ───────────────────────────────────────────────────────

def dias_totales_mes(fecha: datetime) -> int:
    """Devuelve el número de días del mes de la fecha dada."""
    return monthrange(fecha.year, fecha.month)[1]


def dias_restantes_mes(fecha: datetime) -> int:
    """Días que restan en el mes (incluido el día de hoy)."""
    return dias_totales_mes(fecha) - fecha.day + 1


def ultimo_dia_mes(fecha: datetime) -> datetime:
    """Devuelve el último segundo del último día del mes de la fecha dada.

    Ejemplo: fecha=2026-10-15 → 2026-10-31 23:59:59 UTC
    """
    ultimo = dias_totales_mes(fecha)
    return datetime(fecha.year, fecha.month, ultimo, 23, 59, 59, tzinfo=timezone.utc)


def primer_dia_mes_siguiente(fecha: datetime) -> datetime:
    """Devuelve el primer segundo del primer día del mes siguiente.

    Ejemplo: fecha=2026-10-15 → 2026-11-01 00:00:00 UTC
    """
    if fecha.month == 12:
        return datetime(fecha.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    return datetime(fecha.year, fecha.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)


# ── Prorrateo ─────────────────────────────────────────────────────────────────

def calcular_prorrateo(precio_mensual: float, fecha: datetime) -> float:
    """Calcula el monto prorrateado para el mes en curso.

    Fórmula: precio × (días_restantes / días_totales)
    Redondeo: 2 decimales.
    Determinista: mismo precio + fecha → mismo resultado.

    Ejemplos con $50 en octubre (31 días):
        día  1 → $50.00
        día 15 → $27.42
        día 25 → $11.29
        día 30 → $ 3.23
    """
    dias_rest = dias_restantes_mes(fecha)
    dias_tot = dias_totales_mes(fecha)
    monto = precio_mensual * (dias_rest / dias_tot)
    return round(monto, 2)


# ── Validación de clave ───────────────────────────────────────────────────────

def validar_formato_clave(clave: str) -> bool:
    """Valida el formato ALTA-XXXX-XXXX-XXXX-XXXX.

    Caracteres permitidos: A-Z excluyendo I,O (ambigüos) + 2-9 (sin 0,1).
    """
    return bool(_CLAVE_PATRON.match(clave.strip().upper()))


# ── CRUD sobre LicenciaLocal ──────────────────────────────────────────────────

def _obtener_o_crear(db: Session) -> LicenciaLocal:
    """Obtiene la fila de licencia (id=1) o la crea si no existe."""
    lic = db.get(LicenciaLocal, 1)
    if lic is None:
        ahora = datetime.now(timezone.utc)
        lic = LicenciaLocal(
            id=1,
            estado="trial",
            fecha_instalacion=ahora,
            fecha_expiracion_trial=ahora + timedelta(days=TRIAL_DIAS),
            hardware_id=obtener_hardware_id(),
        )
        db.add(lic)
        db.commit()
        db.refresh(lic)
    return lic


def iniciar_si_no_existe(db: Session, email: str = "", hardware_id: str = "") -> None:
    """Crea la licencia si no existe. Si el usuario es founder, marca estado=founder.

    Llamar en startup después de init_db().
    """
    lic = _obtener_o_crear(db)

    # Detectar founder
    hw = hardware_id or obtener_hardware_id()
    if _es_founder_config(email, hw):
        if not lic.es_founder:
            lic.es_founder = True
            lic.estado = "founder"
            db.add(lic)
            db.commit()


def estado_actual(db: Session) -> str:
    """Calcula y devuelve el estado vigente de la licencia.

    El estado almacenado puede quedar desactualizado si el tiempo pasó;
    esta función recalcula en base a fechas reales.

    Retorna uno de: founder | trial | activa | gracia | expirada | bloqueada
    """
    lic = _obtener_o_crear(db)
    ahora = datetime.now(timezone.utc)

    # Normalizar tzinfo: SQLite devuelve naive datetimes
    def _utc(dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    # Founder: siempre activo
    if lic.es_founder:
        return "founder"

    # Verificar hardware (anticopia)
    hw_actual = obtener_hardware_id()
    if lic.hardware_id and lic.hardware_id != hw_actual:
        return "bloqueada"

    # Trial
    exp_trial = _utc(lic.fecha_expiracion_trial)
    if lic.estado == "trial" or lic.clave is None:
        if exp_trial and ahora <= exp_trial:
            return "trial"
        else:
            return "expirada"

    # Activa
    activa_hasta = _utc(lic.activa_hasta)
    if activa_hasta:
        if ahora <= activa_hasta:
            return "activa"
        # Vencida: ¿gracia o expirada?
        dias_vencida = (ahora - activa_hasta).days
        if dias_vencida <= GRACIA_DIAS:
            return "gracia"
        return "expirada"

    return "trial"


def puede_escribir(db: Session) -> bool:
    """True si el estado actual permite operaciones de escritura.

    Escritura permitida en: founder, trial, activa, gracia.
    Solo lectura en: expirada, bloqueada.
    """
    return estado_actual(db) in {"founder", "trial", "activa", "gracia"}


def dias_restantes_trial(db: Session) -> int:
    """Días restantes del período de prueba. 0 si ya vació o no está en trial."""
    lic = _obtener_o_crear(db)
    if lic.fecha_expiracion_trial is None:
        return 0
    ahora = datetime.now(timezone.utc)
    exp = lic.fecha_expiracion_trial
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    delta = (exp - ahora).days
    return max(0, delta)


def dias_restantes_licencia(db: Session) -> int:
    """Días restantes de la licencia activa. 0 si no está activa o ya expiró."""
    lic = _obtener_o_crear(db)
    if lic.activa_hasta is None:
        return 0
    ahora = datetime.now(timezone.utc)
    hasta = lic.activa_hasta
    if hasta.tzinfo is None:
        hasta = hasta.replace(tzinfo=timezone.utc)
    delta = (hasta - ahora).days
    return max(0, delta)


def activar_licencia(db: Session, clave: str) -> dict:
    """Activa la licencia con la clave dada.

    - Si es founder → devuelve estado=founder sin modificar nada.
    - Si formato inválido → error.
    - Si OK → calcula prorrateo, fija activa_hasta=último día del mes.

    Retorna dict con: ok (bool), estado, mensaje, monto_prorrateado.
    """
    lic = _obtener_o_crear(db)

    if lic.es_founder:
        return {"ok": True, "estado": "founder", "mensaje": "Acceso Founder. No requiere licencia.", "monto_prorrateado": 0.0}

    clave = clave.strip().upper()
    if not validar_formato_clave(clave):
        lic.intentos_fallidos += 1
        db.add(lic)
        db.commit()
        return {"ok": False, "estado": lic.estado, "mensaje": "Formato de clave inválido. Use ALTA-XXXX-XXXX-XXXX-XXXX", "monto_prorrateado": None}

    ahora = datetime.now(timezone.utc)
    monto = calcular_prorrateo(lic.precio_mensual, ahora)
    fin_mes = ultimo_dia_mes(ahora)

    lic.clave = clave
    lic.estado = "activa"
    lic.activa_desde = ahora
    lic.activa_hasta = fin_mes
    lic.monto_prorrateado = monto
    lic.intentos_fallidos = 0
    db.add(lic)
    db.commit()

    return {
        "ok": True,
        "estado": "activa",
        "mensaje": f"Licencia activada. Vigente hasta {fin_mes.strftime('%d/%m/%Y')}.",
        "monto_prorrateado": monto,
        "activa_hasta": fin_mes.isoformat(),
    }


def renovar_mes(db: Session) -> dict:
    """Extiende la licencia activa al último día del mes siguiente.

    Solo opera si el estado actual es activa o gracia.
    Retorna dict con: ok, estado, mensaje, activa_hasta.
    """
    lic = _obtener_o_crear(db)
    est = estado_actual(db)

    if lic.es_founder:
        return {"ok": True, "estado": "founder", "mensaje": "Founder: renovación no requerida."}

    if est not in {"activa", "gracia"}:
        return {"ok": False, "estado": est, "mensaje": f"No se puede renovar en estado '{est}'."}

    ahora = datetime.now(timezone.utc)
    nuevo_fin = ultimo_dia_mes(primer_dia_mes_siguiente(ahora))

    lic.activa_hasta = nuevo_fin
    lic.estado = "activa"
    db.add(lic)
    db.commit()

    return {
        "ok": True,
        "estado": "activa",
        "mensaje": f"Renovada hasta {nuevo_fin.strftime('%d/%m/%Y')}.",
        "activa_hasta": nuevo_fin.isoformat(),
    }


def validar_periodicamente(db: Session) -> dict:
    """Recalcula el estado al arrancar o en chequeos periódicos.

    - Founder: siempre activo, sin validar.
    - Trial vencido → expirada.
    - Activa vencida → gracia o expirada.
    - Actualiza el campo `estado` en BD para mantenerlo coherente.

    Retorna dict con estado actualizado.
    """
    lic = _obtener_o_crear(db)

    if lic.es_founder:
        return {"estado": "founder", "mensaje": "Founder activo."}

    nuevo_estado = estado_actual(db)
    if lic.estado != nuevo_estado:
        lic.estado = nuevo_estado
        db.add(lic)
        db.commit()

    return {"estado": nuevo_estado}


def info_licencia(db: Session) -> dict:
    """Devuelve un resumen completo del estado de la licencia.

    Usado por el endpoint GET /api/licencia/estado.
    """
    lic = _obtener_o_crear(db)
    est = estado_actual(db)
    hw = obtener_hardware_id()

    return {
        "estado": est,
        "es_founder": lic.es_founder,
        "hardware_id": hw,
        "dias_restantes_trial": dias_restantes_trial(db),
        "dias_restantes_licencia": dias_restantes_licencia(db),
        "monto_prorrateado": lic.monto_prorrateado,
        "precio_mensual": lic.precio_mensual,
        "activa_hasta": lic.activa_hasta.isoformat() if lic.activa_hasta else None,
        "fecha_expiracion_trial": lic.fecha_expiracion_trial.isoformat() if lic.fecha_expiracion_trial else None,
        "intentos_fallidos": lic.intentos_fallidos,
    }


def obtener_banner_licencia(db: Session) -> Optional[dict]:
    """Genera la estructura de banner para el template base si aplica.

    Retorna None si no hay aviso necesario (ej. founder o activa con > 5 días).
    Retorna dict con {"tipo": "warn"|"error", "mensaje": "..."} si aplica.
    """
    est = estado_actual(db)
    if est == "founder":
        return None

    if est == "bloqueada":
        return {
            "tipo": "error",
            "mensaje": "⚠️ Licencia bloqueada por cambio de hardware. Contacte al soporte o active una nueva clave.",
        }

    if est == "expirada":
        return {
            "tipo": "error",
            "mensaje": "⛔ Período de licencia expirado. El sistema funciona en modo solo lectura.",
        }

    if est == "gracia":
        return {
            "tipo": "warn",
            "mensaje": "⏳ Su licencia ha vencido pero está en período de gracia (7 días). Renueve pronto.",
        }

    if est == "trial":
        dias = dias_restantes_trial(db)
        if dias <= 5:
            return {
                "tipo": "warn",
                "mensaje": f"⚡ Su período de prueba termina en {dias} día(s). Active su clave para continuar sin interrupciones.",
            }
        return None

    if est == "activa":
        dias = dias_restantes_licencia(db)
        if dias <= 5:
            return {
                "tipo": "warn",
                "mensaje": f"📅 Su licencia vence en {dias} día(s). Recuerde renovar antes de fin de mes.",
            }
        return None

    return None

